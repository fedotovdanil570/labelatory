from abc import ABCMeta, abstractmethod
import requests
import aiohttp


class DefaultConnector(metaclass=ABCMeta):
    def __init__(self, user=None, repo=None, token=None):
        self.user = user
        self.repo = repo
        self.token = token
        headers = {
            'User-Agent': 'Labelatory',
            'Authorization': f'token {token}'
        }
        self.session = aiohttp.ClientSession(headers=headers)

    @abstractmethod
    def get_labels(self, repo):
        """ Retrieves labels from repository. """
        raise NotImplementedError('Too generic. Use a subclass for getting labels.')
    
    @abstractmethod
    def get_label(self, repo):
        """ Retrieve label from repository. """
        raise NotImplementedError('Too generic. Use a subclass for getting label.')

    @abstractmethod
    def remove_label(self, repo):
        """ Removes label, which does not conform to configuration. """
        raise NotImplementedError('Too generic. Use a subclass for reverting the label.')

    @abstractmethod
    def create_label(self, repo, label):
        """ Creates new label in given repository. """
        raise NotImplementedError('Too generic. Use a subclass for creating a new label.')

    @abstractmethod
    def update_label(self, repo, label):
        """ Updates existing label in repository. """
        raise NotImplementedError('Too generic. Use a subclass for updating existing label.')


class GitHubConnector(DefaultConnector):
    pass

class GitLabConnector(DefaultConnector):
    pass