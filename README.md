# Labelatory

## Description

Labelatory is a web application for synchronization of labels among repositories stored on diffenrent git services.

This project is a semestral project for course NI-PYT on CTU in Prague.

## Requirements

### Core functionality
The application allows to manage labels (create, update and delete) for given services and repositries according to API of the services. 

* create - if there is a configuration for the label, but repositry doesn't contain this label, create it.
* update - if the configuration for the label has changed, update this label in repositories; if the label in some repository has changed, but configuration didn't, update this label according to configuration.
* delete - if new created label for the repository does not correspond with the configuretion, delete this label.

Work with API runs in asynchronous manner.

### Web Application functionality
The application is built with Flask framework and uses webhooks cofigured for labels events. Once some action with some label in managable repository is performed, the application 
reacts on this event and checks whether the label conforms to configuration. If it does not conform, the application reverts this label.

Web interface displays current preferences for services and repositories that were read by the application from the configuration file.

User can change these preferences at his own discretion - customize already defined labels, add new label, add new repository for service.

Adding support for a new service is provided with implementing the interface for comunnication with git service according to API documentation of the new service.

User can save his customized preferences to configuration file.

### Configuration file example
Credentials cofiguration file is stored locally and contains data for accessing the services and defines, where the label configuration file is stored. 

Credentials cofiguration file example:
```
[config]
type = <type>
repo = github_username/github_config_repo
secret = <GITHUB_WEBHOOK_SECRET>

[service:github]
token = <GITHUB_TOKEN>
secret = <GITHUB_WEBHOOK_SECRET>

[service:gitlab]
host = <host>
token = <GITLAB_TOKEN>
secret = <GITLAB_WEBHOOK_SECRET>
```

* config - defines, where the label configuration file is stored.
  - type (required) - can be "local" or "remote"
  - repo (required for "remote" type) - defines a repo on github, where the label configuration file is stored.
  - secret (required for "remote" type) - defines a webhook secret for repo.
* service.<service_name> (e.g. service.github) - contains "token" for communication with API of the service and "secret" for work with webhooks.
  - token - access token.
  - secret - defines a webhook secret for repo.
  - host (optional) - defines the instance for gitlab case (ex. "gitlab.company.com"). If host key is not defined, the default "gitlab.com" is used.



Labels settings are stored in configuration files. The example of such a file is below:
```
[repo:github]
github_username/github_repo_1 = true
github_username/github_repo_2 = false

[repo:gitlab]
gitlab_username/gitlab_repo_1 = true
gitlab_username/gitlab_repo_2 = false

[label:bug]
color = #123456
description = Indicates an unexpected problem or unintended behavior
```

* repo.<service_name> (e.g. repo.github) - contains repositories on the service to be controlled.
  - "username/repo" can be either "true" or "false" - manages whether repository must be under control or not.
* label.<label_name> - describes features of given label name.
  - "color" - defines the color of the label in hex format.
  - "description" - the descrition of the label.

