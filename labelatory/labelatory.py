import pathlib
import configparser
import distutils.util
import aiohttp
import asyncio
import requests
import base64

from connector import GitHubConnector, GitLabConnector


USER = 'fedotovdanil570'
REPO = 'committee-web-test'

LOCAL_LABELS_CONF_SOURCE = 'labels_conf.cfg'

PATH_REGEX = r'(\/.*?\.[\w:]+)'

RULE_TYPES = ['message', 'path', 'stats']

PLAIN_MATCH_PREFIX = 'plain:'
REGEX_MATCH_PREFIX = 'regex:'
WORDLIST_MATCH_PREFIX = 'wordlist:'

VALID_MESSAGE_AND_PATH_MATCH_TYPES = ['plain', 'regex', 'wordlist']
VALID_RULE_MATCH_FORMAT_REGEX = r'.+:.+'

VALID_FILE_STATUSES = ['modified', 'added', 'removed', '*']

# VALID_STAT_TYPES = ['total', 'additions', 'deletions', 'changes']
VALID_COMMIT_STAT_TYPES = ['total', 'additions', 'deletions']
VALID_FILE_STAT_TYPES = ['additions', 'deletions', 'changes']
VALID_OUTPUT_FORMATS = ['commits', 'rules', 'none']


class LabelatoryConfig():
    """ Stores common configuration for the application. \
        services - supported services;\
        labels_rules - rules for labels;\
        source_secret - secret key for webhook to github repo, \
            where the labels configuration is stored. """
    def __init__(self, services=None, labels_rules=None, source_secret=None):
        self.services = services
        self.labels_rules = labels_rules
        self.source_secrete = source_secret

class Label():
    def __init__(self, name, color, description):
        self.name = name
        self._old_name = name
        self.color = color
        self.description = description

    @classmethod
    def load(cls, cfg_labels):
        pass

class CheckResult():
    def __init__(self, label_name, violations):
        self.label_name = label_name
        self.violations = violations

class Service():
    def __init__(self, token, secret, repos):
        self.token = token
        self.secret = secret
        self.repos = repos
        
    def check(self, labels_rules):
        """ Checks whether all enabled repos of the service correctly defines labels. """
        raise NotImplementedError('Too generic. Use a subclass for check.')

class GitHubService(Service):
    def __init__(self, token, secret, repos, connector=None):
        super().__init__(token, secret, repos)
        if not connector:
            self.connector = GitHubConnector(token)
        else:
            self.connector = connector
        # self.repos = repos
        self._headers = {
            'User-Agent': 'Labelatory',
            'PRIVATE-TOKEN': f'{self.token}'
        }

    async def check(self, labels_rules):
        async with aiohttp.ClientSession(headers=self._headers) as session:
            self.connector.session = session

            results = {}

            for reposlug, enabled in self.repos.items():
                if enabled:
                    status, labels = await self.connector.get_labels(reposlug)
                    if status != 200:
                        raise Exception('Can\'t connect!')

                    checked_labels = {}
                    # Loop on every label in current repository
                    for label in labels:
                        violations = []
                        name = label['name']
                        label_rule = labels_rules.get(name)
                        if label_rule:
                            # Check label parameters. Raise an exception if wrong
                            if label['color'] != label_rule.color[1:]:
                                color = label['color']
                                right_color = label_rule.color
                                violations.append(f'Wrong label color in repository \'{reposlug}\' in label \'{name}\'. Must be \'{right_color}\', found \'{color}\'.')
                                # raise Exception(f'Wrong label color in repository {reposlug} in label {name}. Must be {right_color}, found {color}.')
                            if label['description'] != label_rule.description:
                                description = label['description']
                                right_description = label_rule.description
                                violations.append(f'Wrong label description in repository \'{reposlug}\' in label \'{name}\'. Must be \'{right_description}\', found \'{description}\'.')
                                # raise Exception(f'Wrong label description in repository {reposlug} in label {name}. Must be {right_description}, found {description}.')
                        else:
                            violations.append(f'Wrong label in repository \'{reposlug}\'. Label with name \'{name}\' is not defined.')
                        checked_labels.update({name: violations})
                    # print(f'Repo {reposlug} is OK :)')
                    results.update({reposlug: checked_labels})
            return results

    @classmethod
    def load(cls, cfg, token, secret, repos):
        return GitHubService(
            token,
            secret,
            repos
        )

class GitLabService(Service):
    def __init__(self, token, secret, repos, host=None, connector=None):
        super().__init__(token, secret, repos)
        
        if not host:
            self.host = 'gitlab.com'
        else:
            self.host = host

        if not connector:
            self.connector = GitLabConnector(host, token)
        else:
            self.connector = connector

        self._headers = {
            'User-Agent': 'Labelatory',
            'Authorization': f'token {self.token}'
        }
    
    async def check(self, labels_rules):
        async with aiohttp.ClientSession(headers=self._headers) as session:
            self.connector.session = session

            results = {}

            for reposlug, enabled in self.repos.items():
                if enabled:
                    status, labels = await self.connector.get_labels(reposlug)
                    if status != 200:
                        raise Exception(f'Can\'t connect! {status}')

                    checked_labels = {}
                    # Loop on every label in current repository
                    for label in labels:
                        violations = []
                        name = label['name']
                        label_rule = labels_rules.get(name)
                        if label_rule:
                            # Check label parameters. Raise an exception if wrong
                            if label['color'] != label_rule.color:
                                color = label['color']
                                right_color = label_rule.color
                                violations.append(f'Wrong label color in repository \'{reposlug}\' in label \'{name}\'. Must be \'{right_color}\', found \'{color}\'.')
                                # raise Exception(f'Wrong label color in repository {reposlug} in label {name}. Must be {right_color}, found {color}.')
                            if label['description'] != label_rule.description:
                                description = label['description']
                                right_description = label_rule.description
                                violations.append(f'Wrong label description in repository \'{reposlug}\' in label \'{name}\'. Must be \'{right_description}\', found \'{description}\'.')
                                # raise Exception(f'Wrong label description in repository {reposlug} in label {name}. Must be {right_description}, found {description}.')
                        else:
                            violations.append(f'Wrong label in repository \'{reposlug}\'. Label with name \'{name}\' is not defined.')
                        checked_labels.update({name: violations})
                    # print(f'Repo {reposlug} is OK :)')
                    results.update({reposlug: checked_labels})
            return results

    @classmethod
    def load(cls, cfg, token, secret, repos):
        host = cfg.get('service:gitlab', 'host')
        return GitLabService(
            token,
            secret,
            repos,
            host
        )


class ConfigLoader():
    
    # @classmethod
    # def _load_credentials_config(cls, cgf):

    SUPPORTED_SERVICES = {
        'github': GitHubService,
        'gitlab': GitLabService
    }

    @classmethod
    def _load_label_rule(cls, cfg_labels, label_rule):
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
        service = cls.SUPPORTED_SERVICES[service_name].load(cfg, service_token, service_secret, service_repos)
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
        # config_dir = pathlib.Path(config_file).resolve().parents[0]
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
    parts = reposlug.split('/')
    if len(parts) != 2:
        raise Exception(f'Reposlug {reposlug} is not correct!')
    return reposlug   
        

def load_app(path):
    try:
        cfg = configparser.ConfigParser()
        with open(path) as f:
            cfg.read_file(f)
        return ConfigLoader.load(cfg)
    except Exception as e:
        print(e)


def main():
    print('Hello!')

if __name__ == "__main__":
    services, config = load_app('credentials_conf.cfg')
    # github = services.services[0]
    # repos = github.repos
    # label = Label('my_test_label', '#ffbf00', 'This is my first test label')
    # for repo, enabled in repos.items():
    #     if enabled:
    #         github.connector.get_labels(repo)
    #         _, j = github.connector.create_label(repo,  label)
            
    #         label.name = 'changed_name'
    #         label.description = 'Changed description.'
    #         s, j = github.connector.update_label(repo, label)
    #         # s, j = github.connector.remove_label(repo, label)
    # print(s, j)
    async def _solve_tasks():
        tasks = []
        for service in services:
            task = asyncio.ensure_future(service.check(config.labels_rules))
            tasks.append(task)

        result = await asyncio.gather(return_exceptions=True, *tasks)
        from pprint import pprint
        pprint(result)


    loop = asyncio.get_event_loop()
    loop.run_until_complete(_solve_tasks())
    loop.close()