import aiohttp
import asyncio
import hmac
import hashlib

from .label import *
from .connector import GitHubConnector, GitLabConnector
from flask import Flask, url_for, render_template, request, abort, redirect, jsonify
from flask.wrappers import Response

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