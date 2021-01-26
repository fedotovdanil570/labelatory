from abc import ABCMeta, abstractmethod
import json
import requests
import aiohttp


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
    def get_labels(self, reposlug):
        """ Retrieves labels from repository. """
        raise NotImplementedError('Too generic. Use a subclass for getting labels.')
    
    @abstractmethod
    def get_label(self, reposlug, label):
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
        page = resp.json()
        if not resp.links.get('next'):
            return (resp.status_code, page)
        
        # If there are more pages, get them in ansynchronous manner
        while resp.links.get('next'):
            URL = resp.links['next']['url']
            async with self.session.get(URL) as resp:
                page_content = await resp.json()
                page.extend(page_content)

        return (resp.status, page)

    async def get_label(self, reposlug, label):
        user, repo = reposlug.split('/')
        URL = f'https://api.github.com/repos/{user}/{repo}/labels/{label.name}'

        async with self.session.get(URL) as resp:
            status = resp.status
            label = await resp.json()
        return (status, label)

    async def create_label(self, reposlug, label):
        user, repo = reposlug.split('/')
        URL = f'https://api.github.com/repos/{user}/{repo}/labels'


        data = {
            'name': label.name, 
            'color':label.color[1:], 
            'description':label.description
        }
        # headers = {
        #     'User-Agent': 'Labelatory',
        #     'Authorization': f'token {self.token}'
        # }
        # resp = requests.post(URL, headers=headers, json=data)

        # return (resp.status_code, resp.json())

        async with self.session.post(URL, json=data) as resp:
            resp_status = resp.status
            resp_result = await resp.json()
        return (resp_status, resp_result)

    async def remove_label(self, reposlug, label):
        user, repo = reposlug.split('/')
        URL = f'https://api.github.com/repos/{user}/{repo}/labels/{label.name}'

        # headers = {
        #             'User-Agent': 'Labelatory',
        #             'Authorization': f'token {self.token}'
        # }
        # resp = requests.delete(URL, headers=headers)
        # return resp.status_code

        async with self.session.delete(URL) as resp:
            resp_status = resp.status
        return resp_status

    async def update_label(self, reposlug, label):
        user, repo = reposlug.split('/')
        URL = f'https://api.github.com/repos/{user}/{repo}/labels/{label._old_name}'

        data = {
            'new_name': label.name,
            'color': label.color[1:],
            'description': label.description
        }

        # headers = {
        #     'User-Agent': 'Labelatory',
        #     'Authorization': f'token {self.token}'
        # }

        # resp = requests.patch(URL, headers=headers, json=data)
        # if resp.status_code == 200:
        #     label._old_name = label.name
        # return (resp.status_code, resp.json())

        async with self.session.patch(URL, json=data) as resp:
            resp_status = resp.status
            resp_result = await resp.json()
            if resp_status == 200:
                label._old_name = label.name
        return (resp_status, resp_result)
        

    
class GitLabConnector(DefaultConnector):
    def __init__(self, host=None, token=None, session=None):
        super().__init__(token, session)
        if host:
            self.host = host
        else:
            self.host = 'gitlab.com'
    
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
        page = resp.json()
        if not resp.links.get('next'):
            return (resp.status_code, page)
        
        # If there are more pages, get them in ansynchronous manner
        while resp.links.get('next'):
            URL = resp.links['next']['url']
            async with self.session.get(URL) as resp:
                page_content = await resp.json()
                page.extend(page_content)

        return (resp.status, page)

    async def get_label(self, reposlug, label):
        reposlug = reposlug.replace('/', '%2F')
        URL = f'https://{self.host}/api/v4/projects/{reposlug}/labels/{label.name}'

        async with self.session.get(URL) as resp:
            status = resp.status
            label = await resp.json()
        return (status, label)

    async def create_label(self, reposlug, label):
        reposlug = reposlug.replace('/', '%2F')
        URL = f'https://{self.host}/api/v4/projects/{reposlug}/labels'


        data = {
            'name': label.name, 
            'color':label.color, 
            'description':label.description
        }
        # headers = {
        #     'User-Agent': 'Labelatory',
        #     'Authorization': f'token {self.token}'
        # }
        # resp = requests.post(URL, headers=headers, json=data)

        # return (resp.status_code, resp.json())

        async with self.session.post(URL, json=data) as resp:
            resp_status = resp.status
            resp_result = await resp.json()
        return (resp_status, resp_result)

    async def remove_label(self, reposlug, label):
        reposlug = reposlug.replace('/', '%2F')
        URL = f'https://{self.host}/api/v4/projects/{reposlug}/labels/{label.name}'

        # headers = {
        #             'User-Agent': 'Labelatory',
        #             'Authorization': f'token {self.token}'
        # }
        # resp = requests.delete(URL, headers=headers)
        # return resp.status_code

        async with self.session.delete(URL) as resp:
            resp_status = resp.status
        return resp_status

    async def update_label(self, reposlug, label):
        reposlug = reposlug.replace('/', '%2F')
        URL = f'https://{self.host}/api/v4/projects/{reposlug}/labels/{label._old_name}'

        data = {
            'new_name': label.name,
            'color': label.color,
            'description': label.description
        }

        # headers = {
        #     'User-Agent': 'Labelatory',
        #     'Authorization': f'token {self.token}'
        # }

        # resp = requests.patch(URL, headers=headers, json=data)
        # if resp.status_code == 200:
        #     label._old_name = label.name
        # return (resp.status_code, resp.json())

        async with self.session.patch(URL, json=data) as resp:
            resp_status = resp.status
            resp_result = await resp.json()
            if resp_status == 200:
                label._old_name = label.name
        return (resp_status, resp_result)

    

    