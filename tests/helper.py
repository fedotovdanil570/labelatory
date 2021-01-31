import contextlib
import os
import pathlib


fixtures_dir = pathlib.Path(__file__).parent / 'fixtures'

# Cofigs files paths
labels_configs_dir = fixtures_dir / 'labels_config'
credentials_configs_dir = fixtures_dir / 'credentials_config'

# Configs templates paths
labels_templates_dir = fixtures_dir / 'labels_config_templates'
credentials_templates_dir = fixtures_dir / 'credentials_config_templates'



@contextlib.contextmanager
def env(**kwargs):
    original = {key: os.getenv(key) for key in kwargs}
    os.environ.update({key: str(value) for key, value in kwargs.items()})
    try:
        yield
    finally:
        for key, value in original.items():
            if value is None:
                del os.environ[key]
            else:
                os.environ[key] = value


def credentials_config(name):
    return credentials_configs_dir / name

def labels_config(name):
    return labels_configs_dir / name


try:
    user = os.environ['SERVICE_USER'].strip()
    github_token = os.environ['GITHUB_TOKEN'].strip()
    gitlab_token = os.environ['GITLAB_TOKEN'].strip()
except KeyError:
    raise RuntimeError('You must set SERVICE_USER, GITHUB_TOKEN and GITLAB_TOKEN environ vars')
else:
    for credentials_source in credentials_templates_dir.glob('*.cfg'):
        credentials_target = credentials_configs_dir / credentials_source.name
        credentials_target.write_text(
            credentials_source.read_text().replace('{REAL_GH_TOKEN}', github_token)
        )
    for labels_source in labels_templates_dir.glob('*.cfg'):
        labels_target = labels_configs_dir / labels_source.name
        labels_target.write_text(
            labels_source.read_text().replace('{REAL_GH_TOKEN}', github_token).replace('{REAL_GL_TOKEN}', gitlab_token)
        )
