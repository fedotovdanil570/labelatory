import json
import requests
import aiohttp

from .label import Label
from abc import ABCMeta, abstractmethod

class DefaultConnector(metaclass=ABCMeta):
    def __init__(self, token=None, session=None):
        # self.user = user
        # self.repo = repo
        self.token = token
        headers = {
            'User-Agent': 'Labelatory',
            'Authorization': f'token {token}'
        }
        self.session = session # aiohttp.ClientSession(headers=headers)

    @abstractmethod
    def get_repos(self):
        """ Retrieves repositories of the authenticated user. """
        raise NotImplementedError('Too generic. Use a subclass for getting repositories.')

    @abstractmethod
    def get_labels(self, reposlug):
        """ Retrieves labels from repository. """
        raise NotImplementedError('Too generic. Use a subclass for getting labels.')
    
    @abstractmethod
    def get_label(self, reposlug, label_name):
        """ Retrieve label with specified name from repository. """
        raise NotImplementedError('Too generic. Use a subclass for getting label.')

    @abstractmethod
    def remove_label(self, reposlug, label):
        """ Removes label, which does not conform to configuration. """
        raise NotImplementedError('Too generic. Use a subclass for reverting the label.')

    @abstractmethod
    def create_label(self, reposlug, label):
        """ Creates new label in given repository. """
        raise NotImplementedError('Too generic. Use a subclass for creating a new label.')

    @abstractmethod
    def update_label(self, reposlug, label):
        """ Updates existing label in repository. """
        raise NotImplementedError('Too generic. Use a subclass for updating existing label.')


class GitHubConnector(DefaultConnector):
    
    API_ENDPOINT = 'https://api.github.com/'

    def __init__(self, token=None, session=None):
        super().__init__(token, session)
        
    async def get_repos(self):
        URL = f'https://api.github.com/user/repos'
        payload = {'per_page':100}

        # Get first page of repositories synchronously
        headers = {
            'User-Agent': 'Labelatory',
            'Authorization': f'token {self.token}'
        }
        resp = requests.get(URL, headers=headers, params=payload)
        if resp.status_code != 200:
            raise Exception(resp.text)
        page = resp.json()
        if not resp.links.get('next'):
            return [repo['full_name'] for repo in page]
        
        # If there are more pages, get them in ansynchronous manner
        while resp.links.get('next'):
            URL = resp.links['next']['url']
            async with self.session.get(URL) as resp:
                if resp.status != 200:
                    raise Exception(resp.reason)
                page_content = await resp.json()
                page.extend(page_content)
        return [repo['full_name'] for repo in page]

    async def get_labels(self, reposlug):
        user, repo = reposlug.split('/')
        URL = f'https://api.github.com/repos/{user}/{repo}/labels'
        payload = {'per_page':100}

        # Get first page of labels synchronously
        headers = {
            'User-Agent': 'Labelatory',
            'Authorization': f'token {self.token}'
        }
        resp = requests.get(URL, headers=headers, params=payload)
        if resp.status_code != 200:
            raise Exception(resp.text)
        page = resp.json()
        if not resp.links.get('next'):
            return [Label(label['name'], label['color'], label['description']) for label in page]
        
        # If there are more pages, get them in ansynchronous manner
        while resp.links.get('next'):
            URL = resp.links['next']['url']
            async with self.session.get(URL) as resp:
                if resp.status != 200:
                    raise Exception(resp.reason)
                page_content = await resp.json()
                page.extend(page_content)

        return [Label(label['name'], label['color'], label['description']) for label in page]# (resp.status, page)

    async def get_label(self, reposlug, label_name):
        user, repo = reposlug.split('/')
        URL = f'https://api.github.com/repos/{user}/{repo}/labels/{label_name}'

        async with self.session.get(URL) as resp:
            if resp.status != 200:
                raise Exception(resp.reason)
            resp_label = await resp.json()
        return Label(
            resp_label['name'], 
            resp_label['color'], 
            resp_label['description']
        )

    async def create_label(self, reposlug, label):
        user, repo = reposlug.split('/')
        URL = f'https://api.github.com/repos/{user}/{repo}/labels'
        color = label.color
        if label.color.startswith('#'):
            color = color[1:]
        data = {
            'name': label.name, 
            'color':color, 
            'description':label.description
        }

        async with self.session.post(URL, json=data) as resp:
            if resp.status != 201:
                raise Exception(resp.reason)
            resp_result = await resp.json()

        return Label(
            resp_result['name'], 
            resp_result['color'], 
            resp_result['description']
        )

    async def remove_label(self, reposlug, label):
        user, repo = reposlug.split('/')
        URL = f'https://api.github.com/repos/{user}/{repo}/labels/{label.name}'

        async with self.session.delete(URL) as resp:
            if resp.status != 204:
                raise Exception(resp.reason)

    async def update_label(self, reposlug, label):
        user, repo = reposlug.split('/')
        URL = f'https://api.github.com/repos/{user}/{repo}/labels/{label._old_name}'
        color = label.color
        if label.color.startswith('#'):
            color = color[1:]
        data = {
            'new_name': label.name,
            'color': color,
            'description': label.description
        }

        async with self.session.patch(URL, json=data) as resp:
            if resp.status != 200:
                resp_result = await resp.json()
                raise Exception(resp.reason)
            resp_result = await resp.json()
            label._old_name = label.name
        return label
        

    
class GitLabConnector(DefaultConnector):
    def __init__(self, host=None, token=None, session=None):
        super().__init__(token, session)
        if host:
            self.host = host
        else:
            self.host = 'gitlab.com'

    async def get_repos(self):
        URL = f'https://{self.host}/api/v4/projects'
        payload = {'per_page':100, 'membership':True}

        # Get first page of repositories synchronously
        headers = {
            'User-Agent': 'Labelatory',
            'PRIVATE-TOKEN': f'{self.token}'
        }
        resp = requests.get(URL, headers=headers, params=payload)
        if resp.status_code != 200:
            raise Exception(resp.text)
        page = resp.json()
        if not resp.links.get('next'):
            return [repo['path_with_namespace'] for repo in page]
        
        # If there are more pages, get them in ansynchronous manner
        while resp.links.get('next'):
            URL = resp.links['next']['url']
            async with self.session.get(URL) as resp:
                if resp.status != 200:
                    raise Exception(resp.reason)
                page_content = await resp.json()
                page.extend(page_content)
        return [repo['full_name'] for repo in page]    
    
    async def get_labels(self, reposlug):
        reposlug = reposlug.replace('/', '%2F')
        URL = f'https://{self.host}/api/v4/projects/{reposlug}/labels'
        payload = {'per_page':100}

        # Get first page of labels synchronously
        headers = {
            'User-Agent': 'Labelatory',
            'PRIVATE-TOKEN': f'{self.token}'
        }
        resp = requests.get(URL, headers=headers, params=payload)
        if resp.status_code != 200:
            raise Exception(resp.text)
        page = resp.json()
        if not resp.links.get('next'):
            return [Label(label['name'], label['color'], label['description']) for label in page]
        
        # If there are more pages, get them in ansynchronous manner
        while resp.links.get('next'):
            URL = resp.links['next']['url']
            async with self.session.get(URL) as resp:
                if resp.status != 200:
                    raise Exception(resp.reason)
                page_content = await resp.json()
                page.extend(page_content)

        return [Label(label['name'], label['color'], label['description']) for label in page]

    async def get_label(self, reposlug, label_name):
        reposlug = reposlug.replace('/', '%2F')
        URL = f'https://{self.host}/api/v4/projects/{reposlug}/labels/{label_name}'

        async with self.session.get(URL) as resp:
            if resp.status != 200:
                raise Exception(resp.reason)
            resp_label = await resp.json()
        return Label(
            resp_label['name'], 
            resp_label['color'], 
            resp_label['description']
        )

    async def create_label(self, reposlug, label):
        reposlug = reposlug.replace('/', '%2F')
        URL = f'https://{self.host}/api/v4/projects/{reposlug}/labels'

        data = {
            'name': label.name, 
            'color':label.color, 
            'description':label.description
        }

        async with self.session.post(URL, json=data) as resp:
            if resp.status != 201:
                raise Exception(resp.reason)
            resp_result = await resp.json()

        return Label(
            resp_result['name'], 
            resp_result['color'], 
            resp_result['description']
        )

    async def remove_label(self, reposlug, label):
        reposlug = reposlug.replace('/', '%2F')
        URL = f'https://{self.host}/api/v4/projects/{reposlug}/labels/{label.name}'

        async with self.session.delete(URL) as resp:
            if resp.status != 204:
                raise Exception(resp.reason)

    async def update_label(self, reposlug, label):
        reposlug = reposlug.replace('/', '%2F')
        URL = f'https://{self.host}/api/v4/projects/{reposlug}/labels/{label._old_name}'

        data = {
            'new_name': label.name,
            'color': label.color,
            'description': label.description
        }

        async with self.session.patch(URL, json=data) as resp:
            if resp.status != 200:
                raise Exception(resp.reason)
            resp_result = await resp.json()
            label._old_name = label.name
        return label

    

    