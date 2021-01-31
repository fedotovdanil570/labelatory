import json
import flask
import importlib

from helper import env, credentials_config, labels_config


credentials_config_env = credentials_config('app.cfg')
labels_config_env = labels_config('app_labels.cfg')


def _import_app():
    import labelatory
    importlib.reload(labelatory) 
    if hasattr(labelatory, 'app'):
        return labelatory.app
    elif hasattr(labelatory, 'create_app'):
        return labelatory.create_app(None)
    else:
        raise RuntimeError("Can't find a Flask app. ")


def _test_app():
    app = _import_app()
    app.config['TESTING'] = True
    return app.test_client()


def test_app_imports():
    with env(LABELATORY_CONFIG=credentials_config_env):
        app = _import_app()
        assert isinstance(app, flask.Flask)

def test_app_get_has_repos():
    with env(COMMITTEE_CONFIG=credentials_config_env):
        app = _test_app()
        text = app.get('/').get_data(as_text=True)
        assert 'ENABLED' in text
        assert 'bug' in text
        assert '#d73a4a' in text


PAYLOAD = {
    'zen': 'Keep it logically awesome.',
    'hook_id': 123456,
    'hook': {
        'type': 'Repository',
        'id': 55866886,
        'name': 'web',
        'active': True,
        'events': [
            'push',
        ],
        'config': {
            'content_type': 'json',
            'insecure_ssl': '0',
            'secret': 'labelatory',
        },
    },
    'repository': {
        'id': 123456,
        'name': 'labelatory',
        'full_name': 'fedotovdanil570/labelatory',
        'private': False,
    },
    'sender': {
        'login': 'user',
    },
}


def test_ping_pong():
    with env(COMMITTEE_CONFIG=credentials_config_env):
        app = _test_app()
        rv = app.post('/labels', json=PAYLOAD, headers={
            'X-Hub-Signature': 'sha1=313daf03970603e3d53ce9c235a91310869278ec',
            'X-GitHub-Event': 'ping'})
        assert rv.status_code == 200


def test_bad_secret():
    with env(COMMITTEE_CONFIG=credentials_config_env):
        app = _test_app()
        rv = app.post('/labels', json=PAYLOAD, headers={
            'X-Hub-Signature': 'sha1=1cacacc4207bdd4a51a7528bd9a5b9d6546b0c22',
            'X-GitHub-Event': 'ping'})
        assert rv.status_code >= 400


ADDING_LABEL = {
    'name': 'test_adding_label',
    'color': '#ffffff',
    'description': 'Add new test label'
}

def test_add_label_page():
    with env(COMMITTEE_CONFIG=credentials_config_env):
        app = _test_app()
        rv = app.get('/add')
        assert rv.status_code == 200

        text = rv.get_data(as_text=True)
        assert 'Add new label' in text
        assert 'Name:' in text
        assert 'Color:' in text
        assert 'Description:' in text
        

def test_add_label():
    with env(COMMITTEE_CONFIG=credentials_config_env):
        app = _test_app()
        rv = app.post('/add', json=ADDING_LABEL)
        assert rv.status_code == 302

def test_add_existing_label():
    with env(COMMITTEE_CONFIG=credentials_config_env):
        app = _test_app()
        rv = app.post('/add', json=ADDING_LABEL)
        assert rv.status_code == 302

        rv = app.post('/add', json=ADDING_LABEL)
        assert rv.status_code == 400
        assert rv.json['error'] == 'Such a label already defined.'

def test_edit_label_page():
    with env(COMMITTEE_CONFIG=credentials_config_env):
        app = _test_app()

        rv = app.post('/add', json=ADDING_LABEL)
        assert rv.status_code == 302

        rv = app.get(
            '/edit',
            query_string={
                'name': ADDING_LABEL['name'], 
                'oldName': ADDING_LABEL['name'], 
                'color': ADDING_LABEL['color'], 
                'description': ADDING_LABEL['description']
            }
        )
        assert rv.status_code == 200

        text = rv.get_data(as_text=True)
        assert 'Edit label' in text
        assert 'Name:' in text
        assert 'Color:' in text
        assert 'Description:' in text

def test_edit_label():
    with env(COMMITTEE_CONFIG=credentials_config_env):
        app = _test_app()

        rv = app.post('/add', json=ADDING_LABEL)
        assert rv.status_code == 302

        ADDING_LABEL['oldName'] = ADDING_LABEL['name']
        ADDING_LABEL['name'] = 'changed name'

        rv = app.put('/edit', json=ADDING_LABEL)
        assert rv.status_code == 302
        
        rv = app.get('/')
        text = rv.get_data(as_text=True)
        assert 'changed name' in text
        assert ADDING_LABEL['color'] in text
        assert ADDING_LABEL['description'] in text

def test_delete_label():
    with env(COMMITTEE_CONFIG=credentials_config_env):
        app = _test_app()

        rv = app.post('/add', json=ADDING_LABEL)
        assert rv.status_code == 302

        rv = app.delete('/', json=ADDING_LABEL)
        assert rv.status_code == 200

def test_delete_nonexisting_label():
    with env(COMMITTEE_CONFIG=credentials_config_env):
        app = _test_app()

        rv = app.delete('/', json=ADDING_LABEL)
        assert rv.status_code == 404

def test_save_config():
    with env(COMMITTEE_CONFIG=credentials_config_env):
        app = _test_app()
        rv = app.post('/config', )
        pass
