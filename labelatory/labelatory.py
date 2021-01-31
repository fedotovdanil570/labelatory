import os
import pathlib
import configparser
import distutils.util
import aiohttp
import asyncio
from flask.wrappers import Response
import requests
import base64
import json
import hmac
import hashlib


from .label import Label
from .connector import GitHubConnector, GitLabConnector

from flask import Flask, url_for, render_template, request, abort, redirect, jsonify


LOCAL_LABELS_CONF_SOURCE = 'labels_conf.cfg'


class LabelatoryConfig():
    """ Stores common configuration for the application. \
        services - supported services;\
        labels_rules - rules for labels; """
    def __init__(self, services=None, labels_rules=None, source_secret=None):
        self.services = services
        self.labels_rules = labels_rules
        self.source_secrete = source_secret


class Violation():
    """ Holds the violation. Can be color, description or name """
    def __init__(self, type, label, found=None, required=None):
        self.label = label
        self.type = type
        self.required = required
        self.found = found

class Service():
    def __init__(self, name, token, secret, repos):
        self.name = name
        self.token = token
        self.secret = secret
        self.repos = repos
        
    
    async def fix_labels(self, reposlug, labels_rules, labels=None, action=None):
        """ Checks single label. If only name is provided, gets the label from the service. """
        async with aiohttp.ClientSession(headers=self._headers) as session:
            labels_rules_copy = labels_rules.copy()
            results = []
            for label in labels:
                label_name = label.name
                label_rule = labels_rules_copy.get(label_name)

                if label_rule:
                    if action == 'deleted':
                        results.append(await self.fix_violation(labels_rules, reposlug, Violation('missing', label, required=label.name)))
                    
                    # Get parameters of retrieved label
                    label_color = label.color
                    label_description = label.description
                    if label_color[0] == '#':
                        label_color = label_color[1:]
                    
                    # Check label parameters
                    if label_color != label_rule.color[1:]:
                        right_color = label_rule.color
                        results.append(await self.fix_violation(labels_rules, reposlug, Violation('color', label, label_color, right_color)))
                    else:
                        results.append(True)
                    if label_description != label_rule.description:
                        right_description = label_rule.description
                        results.append(await self.fix_violation(labels_rules, reposlug, Violation('description', label, label_description, right_description)))
                    else:
                        results.append(True)
                    # Remove checked label from rules for this reposlug
                    labels_rules_copy.pop(label_name)
                else:
                    # violations.append(Violation('extra', label, label_name))
                    results.append(await self.fix_violation(labels_rules, reposlug, Violation('extra', label, label_name)))

            return all(results)


    async def check_all(self, labels_rules):
        async with aiohttp.ClientSession(headers=self._headers) as session:
            self.connector.session = session

            results = {}

            for reposlug, enabled in self.repos.items():
                if enabled:
                    labels_rules_copy = labels_rules.copy()
                    labels = await self.connector.get_labels(reposlug)

                    # Loop on every label in current repository
                    violations = []
                    for label in labels:
                        label_name = label.name
                        label_rule = labels_rules_copy.get(label_name)

                        if label_rule:
                            # Get parameters of retrieved label
                            label_color = label.color
                            label_description = label.description
                            if label_color[0] == '#':
                                label_color = label_color[1:]
                            # Check label parameters
                            if label_color != label_rule.color[1:]:
                                right_color = label_rule.color
                                violations.append(Violation('color', label, label_color, right_color))
                            if label_description != label_rule.description:
                                right_description = label_rule.description
                                violations.append(Violation('description', label, label_description, right_description))
                            # Remove checked label from rules for this reposlug
                            labels_rules_copy.pop(label_name)
                        else:
                            violations.append(Violation('extra', label, label_name))
                        
                    # Include missing labels
                    violations.extend([Violation('missing', label, required=label.name) for label in labels_rules_copy.values()])
                    
                    # Update results for this service
                    results.update({reposlug: violations})
            return (self, results)

    async def fix_violation(self, labels_rules, reposlug, violation):
        async with aiohttp.ClientSession(headers=self._headers) as session:
            self.connector.session = session
            if violation.type == 'color':
                # Update label with right color
                correct_label = labels_rules.get(violation.label.name)
                violation.label.color = correct_label.color
                await self.connector.update_label(reposlug, violation.label)
            elif violation.type == 'description':
                # Update label with right description
                correct_label = labels_rules.get(violation.label.name)
                violation.label.description = correct_label.description
                await self.connector.update_label(reposlug, violation.label)
            elif violation.type == 'extra':
                # Delete extra label
                await self.connector.remove_label(reposlug, violation.label)
            elif violation.type == 'missing':
                # Create missing label
                await self.connector.create_label(reposlug, violation.label)
        return True

    async def fix_all(self, labels_rules, checked_repos):
        results = {}
        for reposlug, violations in checked_repos.items():
            solved = []
            results[reposlug]= solved
            for violation in violations:
                solved.append(await self.fix_violation(labels_rules, reposlug, violation))
            
        return (self, results)

        

class GitHubService(Service):
    def __init__(self, name, token, secret, repos, connector=None):
        super().__init__(name, token, secret, repos)
        if not connector:
            self.connector = GitHubConnector(token)
        else:
            self.connector = connector
        # self.repos = repos
        self._headers = {
            'User-Agent': 'Labelatory',
            'Authorization': f'token {self.token}'
        }

    def check_secret(self, request):
        """ Checks secret for webhook. """
        signature = request.headers["X-Hub-Signature"]

        if not signature or not signature.startswith("sha1="):
            abort(400, "X-Hub-Signature required")

        payload = request.data
        digest = hmac.new(self.secret.encode(), payload, hashlib.sha1).hexdigest()

        return hmac.compare_digest(signature, "sha1=" + digest)

    def webhook(self, request, labels_rules):
        """ Processes webhook request. """
        async def _fix_labels():
            repository = request.json['repository']['full_name']
            if self.repos.get(repository):
                action = request.json['action']
                # if action == 'created' or action == 'edited':
                label = request.json['label']
                return await self.fix_labels(
                    repository, 
                    labels_rules, 
                    [Label(label['name'], label['color'], label['description'])],
                    action
                )
            else:
                abort(400, 'Repository is not supported')

        if self.check_secret(request):
            event_type = request.headers['X-Github-Event']
            if event_type == 'ping':
                return 'OK', 200
            else:
                asyncio.set_event_loop(asyncio.SelectorEventLoop())
                loop = asyncio.get_event_loop()
                results = loop.run_until_complete(_fix_labels())
                loop.close()
                if results:
                    response = Response(
                        response='OK',
                        status=200,
                    )
                    return response
                else:
                    response = Response(
                        response='Something wrong',
                        status=500
                    )
                    return response
        else:
            abort(400, "Invalid secret")            

    @classmethod
    def load(cls, cfg, name, token, secret, repos):
        return GitHubService(
            name,
            token,
            secret,
            repos
        )



class GitLabService(Service):
    def __init__(self, name, token, secret, repos, host=None, connector=None):
        super().__init__(name, token, secret, repos)
        
        if not host:
            self.host = 'gitlab.com'
        else:
            self.host = host

        if not connector:
            self.connector = GitLabConnector(host, token)
        else:
            self.connector = connector

        self._supported_events = ['issue hook', 'merge request hook', 'note hook']
        
        self._headers = {
            'User-Agent': 'Labelatory',
            'PRIVATE-TOKEN': f'{self.token}'
        }

    def check_secret(self, request):
        """ Checks secret for webhook. """
        secret = request.headers["X-Gitlab-Token"]
        return secret == self.secret

    def webhook(self, request, labels_rules):
        """ Processes webhook request. """
        async def _fix_labels():
            repository = request.json['project']['path_with_namespace']
            if self.repos.get(repository):
                event_type = request.headers['X-Gitlab-Event'].lower()
                if event_type == 'issue hook' or event_type == 'merge request hook':
                    labels = request.json['labels'] 
                else:
                    if request.json['object_attributes']['noteable_type'].lower() == 'issue':
                        labels = request.json['issue']['labels']
                    else:
                        abort(400, 'Bad notable type')
                
                labels_ = [Label(label['title'], label['color'], label['description']) for label in labels]
                
                return await self.fix_labels(
                    repository, 
                    labels_rules, 
                    labels_
                )
            else:
                abort(400, 'Repository is not supported')

        if self.check_secret(request):
            event_type = request.headers['X-Gitlab-Event'].lower()
            if event_type in self._supported_events:
                asyncio.set_event_loop(asyncio.SelectorEventLoop())
                loop = asyncio.get_event_loop()
                results = loop.run_until_complete(_fix_labels())
                loop.close()
                if results:
                    response = Response(
                        response='OK',
                        status=200,
                    )
                    return response
                else:
                    response = Response(
                        response='Something wrong',
                        status=500
                    )
                return response
            else:
                abort(400, "Invalid event")
        else:
            abort(400, "Invalid secret")    

    @classmethod
    def load(cls, cfg, name, token, secret, repos):
        host = cfg.get('service:gitlab', 'host')
        return GitLabService(
            name,
            token,
            secret,
            repos,
            host
        )


class ConfigLoader():
    
    SUPPORTED_SERVICES = {
        'github': GitHubService,
        'gitlab': GitLabService
    }

    @classmethod
    def _load_label_rule(cls, cfg_labels, label_rule):
        """ Loads labels configuration. """
        label_name = label_rule[6:]
        label_color = cfg_labels.get(label_rule, 'color')
        label_description = cfg_labels.get(label_rule, 'description')
        return Label(
            label_name,
            label_color,
            label_description
        )
        
    @classmethod
    def _load_service(cls, cfg, cfg_labels, service):
        """ Loads git service with given configuration. """
        service_name = service[8:]
        service_token = cfg.get(service, 'token')
        service_secret = cfg.get(service, 'secret')
        
        # Loads repos and labels configs
        service_repos = {}
        for repo, status in cfg_labels['repo:'+service_name].items():
            repo = validate_reposlug(repo)
            service_repos[repo] = bool(distutils.util.strtobool(status))
        # service_repos = {repo:bool(distutils.util.strtobool(enabled)) for repo, enabled in cfg_labels['repo:'+service_name].items()}#(s for s in cfg_labels.sections() if s.startswith('repo:'+service_name))
        service = cls.SUPPORTED_SERVICES[service_name].load(cfg, service_name, service_token, service_secret, service_repos)
        return service

    @classmethod
    def _load_remote_labels_config(cls, source, token):
        """ Loads labels configuration file from remote repository on GitHub. """
        validate_reposlug(source)
        user, repo = source.split('/')

        # Get labels configuration file from repository
        URL = f'https://api.github.com/repos/{user}/{repo}/contents/labels_conf.cfg'
        headers = {
                    'User-Agent': 'Labelatory',
                    'Authorization': f'token {token}'
                  }
        resp = requests.get(URL, headers=headers)
        if resp.status_code != 200:
            raise Exception(f'Can\'t download labels configuration file from \'{source}\'.')

        # Decode file content from base64 to string
        content = str(base64.b64decode(resp.json()['content']), 'utf-8')

        cfg = configparser.ConfigParser()
        cfg.read_string(content)
        return cfg
        # try:
        #     cfg = configparser.ConfigParser()
        #     cfg.read_string(content)
        #     return cfg
        # except Exception as e:
        #     raise e

    @classmethod
    def _load_local_labels_config(cls):
        """ Loads labels configuration file from local file system. """
        cfg = configparser.ConfigParser()
        with open(LOCAL_LABELS_CONF_SOURCE) as f:
            cfg.read_file(f)
        return cfg
        # try:
        #     cfg = configparser.ConfigParser()
        #     with open(LOCAL_LABELS_CONF_SOURCE) as f:
        #         cfg.read_file(f)
        #     return cfg
        # except Exception as e:
        #     raise e
    
    @classmethod
    def load(cls, cfg):
        """" Loads configuration. """
        labels_conf_type = cfg.get('config', 'type')
        service_sections = (s for s in cfg.sections() if s.startswith('service:'))
        remote_secret = None

        if labels_conf_type == 'remote':
            remote_source = cfg.get('config', 'repo')
            remote_token = cfg.get('config', 'token')
            remote_secret = cfg.get('config', 'secret')
            cfg_labels = cls._load_remote_labels_config(remote_source, remote_token)
        elif labels_conf_type == 'local':
            cfg_labels = cls._load_local_labels_config()
        else:
            raise Exception('Failed to load configuration! \
                Configuration type can be only \'local\' or \'remote\'!')

        label_sections = (s for s in cfg_labels.sections() if s.startswith('label:'))
        services=[cls._load_service(cfg, cfg_labels, service) for service in service_sections]
        return services, LabelatoryConfig(
            # Loads every supported service
            labels_rules={label_rule[6:]: cls._load_label_rule(cfg_labels, label_rule) for label_rule in label_sections},
            source_secret=remote_secret
        )


def validate_reposlug(reposlug):
    """ Validates reposlug. """
    parts = reposlug.split('/')
    if len(parts) != 2:
        raise Exception(f'Reposlug {reposlug} is not correct!')
    return reposlug   
        

def load_app(path):
    """ Loads app. """
    try:
        cfg = configparser.ConfigParser()
        with open(path) as f:
            cfg.read_file(f)
        return ConfigLoader.load(cfg)
    except Exception as e:
        print(e)
        exit(1)


def fix_labels_async_wrapper(cfg):
    """ Fixes labels of all enabled repositories for all supported services.  """
    services = cfg['services']
    labels_rules = cfg['cfg']
    from pprint import pprint
    async def _solve_tasks():
        tasks = []
        for service in services:
            task = asyncio.ensure_future(service.check_all(labels_rules))
            tasks.append(task)
        results = await asyncio.gather(return_exceptions=True, *tasks)
        pprint(results)

        tasks = []
        for result in results:
            service, checked_repos = result
            if checked_repos:
                task = asyncio.ensure_future(service.fix_all(labels_rules, checked_repos))
                tasks.append(task)
        print(tasks)

        results = await asyncio.gather(return_exceptions=True, *tasks)
        # pprint(results)
        return results

    asyncio.set_event_loop(asyncio.SelectorEventLoop())
    loop = asyncio.get_event_loop()
    results = loop.run_until_complete(_solve_tasks())
    loop.close()
    return results

def check_labels_async_wrapper(cfg):
    services = cfg['services']
    labels_rules = cfg['cfg']
    from pprint import pprint
    async def _solve_tasks():
        tasks = []
        for service in services:
            task = asyncio.ensure_future(service.check_all(labels_rules))
            tasks.append(task)

        results = await asyncio.gather(return_exceptions=True, *tasks)
        # pprint(results)
        return results

        # tasks = []
        # for result in results:
        #     service, checked_repos = result
        #     if checked_repos:
        #         task = asyncio.ensure_future(service.fix_all(labels_rules, checked_repos))
        #         tasks.append(task)
        # print(tasks)

        # results = await asyncio.gather(return_exceptions=True, *tasks)
        # pprint(results)

    asyncio.set_event_loop(asyncio.SelectorEventLoop())
    loop = asyncio.get_event_loop()
    results = loop.run_until_complete(_solve_tasks())
    loop.close()
    return results

def get_repos_for_service_async_wrapper(service):

    asyncio.set_event_loop(asyncio.SelectorEventLoop())
    loop = asyncio.get_event_loop()
    repos = asyncio.ensure_future(service.connector.get_repos())

    results = loop.run_until_complete(repos)
    loop.close()
    return results

ENVVAR_CONFIG = 'LABELATORY_CONFIG'
def load_web(app):
    if ENVVAR_CONFIG not in os.environ:
        app.logger.critical(f'Config not supplied by envvar {ENVVAR_CONFIG}')
        exit(1)
    config_file_path = os.environ[ENVVAR_CONFIG]
    return load_app(config_file_path)

def main():
    print('Hello!')

def create_app(config=None):
    app = Flask(__name__)
    
    app.logger.info('Loading Labelatory configuration...')
    services, cfg = load_web(app)
    cfg_ = {}
    for key in sorted(cfg.labels_rules.keys()):
        cfg_[key] = cfg.labels_rules[key]
    app.config['cfg'] = cfg_
    app.config['services'] = services
    app.config['cfg_secret'] = cfg.source_secrete

    app.logger.info('Labelatory is completely loaded now.')

    @app.route('/', methods=['GET', 'POST', 'DELETE'])
    def index():
        """ Returns the landing page on GET request.
        Enables/disables avaliable repositories for supported services on POST request.
        Deletes chosen label on DELETE request. """
        if request.method == 'POST':
            # Enabling/disabling repositories
            data = request.json
            
            services_ = app.config['services']
            for service in services_:
                if service.name == data['service']:
                    service.repos[data['reposlug']] = bool(distutils.util.strtobool(data['enabled']))
            return redirect(url_for('index'))
        elif request.method == 'DELETE':
            # Delete labels
            data = request.json
            labels_rules = app.config['cfg'] # .labels_rules

            if labels_rules.get(data['name']):
                labels_rules.pop(data['name'])  

                response = app.response_class(
                            response='OK',
                            status=200
                        )
                return response
            else:
                return 'Not found', 404
        else:
            # Return landing
            return render_template(
                'index.html',
                cfg=app.config['cfg'],
                services=services
            )

    @app.route('/add', methods=['GET', 'POST'])
    def add_label():
        """ Adds a new label """
        if request.method == 'POST':
            data = request.json
            new_label = Label(
                data['name'],
                data['color'],
                data['description']
            )
            if not app.config['cfg'].get(new_label.name):
                app.config['cfg'].update({new_label.name: new_label})
                cfg_ = {}
                # Ordering labels
                for key in sorted(app.config['cfg'].keys()):
                    cfg_[key] = app.config['cfg'][key]
                app.config['cfg'] = cfg_
            else:
                response = app.response_class(
                    response=json.dumps({"error": "Such a label already defined."}),
                    status=400,
                    mimetype='application/json'
                )
                return response
            return redirect(url_for('index'))
        else:    
            return render_template(
                'add_label.html',
                cfg=app.config['cfg']
            )

    @app.route('/edit', methods=['GET', 'PUT'])
    def edit_label():
        """ Edits chosen label. """
        if request.method == 'PUT':
            # Convert data to Label object
            data = request.json
            old_name = data['oldName']
            edited_label = Label(
                data['name'],
                data['color'],
                data['description']
            )
            app.config['cfg'].pop(old_name)
            app.config['cfg'].update({edited_label.name: edited_label})
            # Ordering labels
            cfg_ = {}
            for key in sorted(app.config['cfg'].keys()):
                cfg_[key] = app.config['cfg'][key]
            app.config['cfg'] = cfg_
            return redirect(url_for('index'))
        else:
            return render_template(
                'edit_label.html',
                cfg=app.config['cfg']
            )
    
    @app.route('/labels', methods=['POST'])
    def webhook():
        """ Reacts on webhooks of supported services. """
        for header, value in request.headers.items():
            header_ = header.lower()
            if header_.startswith('x-') and header_.endswith('-event'):
                source = header_.split('-')[1]
                for service in app.config['services']:
                    # Once service is found, 
                    # process the request with webhook method of the service
                    if service.name == source:
                        res = service.webhook(request, app.config['cfg'])
                        return res
                
        # If there is not 'x-*****-event' header
        response = app.response_class(
                    response=json.dumps({"error": "Service is not supported."}),
                    status=400,
                    mimetype='application/json'
                )
        return response    


    @app.route('/config', methods=['POST'])
    def save_config():
        """ Saves current configuration, obtained from web interface locally. """
        config = configparser.ConfigParser()

        # Save services settings
        for service in app.config['services']:
            section_name = f'repo:{service.name}'
            config.add_section(section_name)
            for reposlug, enabled in service.repos.items():
                config.set(section_name, reposlug, str(enabled).lower())

        # Save labels settings
        for label_name, label in app.config['cfg'].items():
            section_name = f'label:{label.name}'
            config.add_section(section_name)
            config.set(section_name, 'color', label.color)
            config.set(section_name, 'description', label.description)
        
        # with open(ENVVAR_CONFIG, 'w') as config_file:
        # 'test.cfg'
        with open(LOCAL_LABELS_CONF_SOURCE, 'w') as config_file:
            config.write(config_file)
        
        # return '200'
        response = app.response_class(
                        response='OK',
                        status=200
                    )
        return response

    @app.route('/repos', methods=['GET', 'POST'])
    def repos():
        """ Management of available repositories """
        if request.method == 'GET':
            service_name = request.args.get('service')
            services_ = app.config['services']
            for service_ in services_:
                if service_.name == service_name:
                    repos = []
                    repos_ = get_repos_for_service_async_wrapper(service_)
                    used_repos = service_.repos.keys()
                    for repo in repos_:
                        if repo not in used_repos:
                            repos.append(repo)
                    # repos = json.dumps({service_name: repos})
                    return render_template(
                        'add_repo.html',
                        service=service_name,
                        repos=repos
                    )
        else:
            selected_service = [key for key in request.json.keys()]
            selected_service = selected_service[0]
            selected_repos = request.json[selected_service]

            services_ = app.config['services']
            for service_ in services_:
                if service_.name == selected_service:
                    for repo in selected_repos:
                        service_.repos.update({repo: True})
                    break

            return redirect(url_for('index'))

    # @app.route('/check', methods=['GET', 'POST'])
    # def check_l():
    #     if request.method == 'GET':
    #         enabled_ = {}
    #         services_ = app.config['services']
    #         for service_ in services_:
    #             repos = []
    #             for repo, enabled in service_.repos.items():
    #                 if enabled:
    #                     repos.append(repo)
    #             if repos:
    #                 enabled_[service_.name] = repos
            
    #         print(enabled_)
    #         return render_template(
    #             'check_labels.html',
    #             services = enabled_# app.config['services']
    #         )
    #     else:
    #         check_labels_async_wrapper(app.config)
    #         # return '200'
    #         response = app.response_class(
    #                     response='OK',
    #                     status=200
    #                 )
    #         return response

    @app.route('/check/labels', methods=['GET', 'POST'])
    def check_labels():
        if request.method == 'GET':
            check_results = check_labels_async_wrapper(app.config)
            data = {}
            for result in check_results:
                service, repos = result
                if repos:
                    reposlugs = []
                    for reposlug, violations in repos.items():
                        if violations:
                            reposlugs.append(reposlug)
                    if reposlugs:
                        data[service.name] = reposlugs

            print(data)
            return jsonify(data)
        else:
            fix_results = fix_labels_async_wrapper(app.config)
            data = {}
            for result in fix_results:
                service, repos = result
                if repos:
                    reposlugs = []
                    for reposlug, fixes in repos.items():
                        if all(fixes):
                            reposlugs.append(reposlug)
                    data[service.name] = reposlugs

            print(data)
            return jsonify(data)
      
    # import time
    # @app.route('/test', methods=['GET'])
    # def test_async():
    #     #code block
    #     async def download_site(session, url):
    #         async with session.get(url) as response:
    #             print("Read {0} from {1}".format(response.content_length, url))


    #     async def download_all_sites(sites):
    #         async with aiohttp.ClientSession() as session:
    #             tasks = []
    #             for url in sites:
    #                 task = asyncio.ensure_future(download_site(session, url))
    #                 tasks.append(task)
    #             await asyncio.gather(*tasks, return_exceptions=True)

    #     sites = ["https://www.jython.org","http://olympus.realpython.org/dice"]*20
    #     start_time = time.time()
    #     asyncio.set_event_loop(asyncio.SelectorEventLoop())
    #     asyncio.get_event_loop().run_until_complete(download_all_sites(sites))
    #     duration = time.time() - start_time
    #     return jsonify({"status":f"Downloaded {len(sites)} sites in {duration} seconds"})
        #end of code block
    
    
    
    return app