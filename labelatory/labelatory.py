import pathlib
import configparser
import distutils.util
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
    def __init__(self, services, labels_rules=None, source_secret=None):
        self.services = services
        self.labels_rules = labels_rules
        self.source_secrete = source_secret

class Label():
    def __init__(self, type, color, description):
        self.type = type
        self.color = color
        self.description = description

    @classmethod
    def load(cls, cfg_labels):
        pass

class Service():
    def __init__(self, token, secret, repos):
        self.token = token
        self.secret = secret
        repos = repos
        
    def check(self):
        """ Checks whether all enabled repos of the service correctly defines labels. """
        raise NotImplementedError('Too generic. Use a subclass for check.')

class GitHubService(Service):
    def __init__(self, token, secret, repos, connector=None):
        super().__init__(token, secret, repos)
        if not connector:
            self.connector = GitHubConnector()
        else:
            self.connector = connector

    def check(self):
        pass

    @classmethod
    def load(cls, cfg_labels, token, secret, repos):
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
            self.connector = GitLabConnector()
        else:
            self.connector = connector
    
    def check(self):
        pass


class ConfigLoader():
    
    # @classmethod
    # def _load_credentials_config(cls, cgf):

    SUPPORTED_SERVICES = {
        'github': GitHubService,
        'gitlab': GitLabService
    }

    @classmethod
    def _load_label_rule(cls, cfg_labels, label_rule):
        label_type = label_rule[6:]
        label_color = cfg_labels.get(label_rule, 'color')
        label_description = cfg_labels.get(label_rule, 'description')
        return Label(
            label_type,
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
        service = cls.SUPPORTED_SERVICES[service_name].load(cfg_labels, service_token, service_secret, service_repos)
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

        return LabelatoryConfig(
            # Loads every supported service
            services=[cls._load_service(cfg, cfg_labels, service) for service in service_sections],
            labels_rules=[cls._load_label_rule(cfg_labels, label_rule) for label_rule in label_sections],
            source_secret=remote_secret
        )

        

def validate_reposlug(reposlug):
    parts = reposlug.split('/')
    if len(parts) != 2:
        raise Exception(f'Reposlug {reposlug} is not correct!')
    return reposlug   
        

def load_config(path):
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
    config = load_config('credentials_conf.cfg')
    print('End.')