from setuptools import setup, find_packages

with open('README.md', 'r') as f:
    # long_description = ''.join(f.readlines())
    long_description = ''
    lines = f.readlines()
    readme = []
    for line in lines:
        if not line.startswith(('## Passed', '### Package', '<p>', '</p>', '<img')):
            readme.append(line)
    long_description = long_description.join(readme)

setup(
    name='labelatory',
    version='0.1',
    description='Labelatory - the powerful and the greatest tool\
         for label management across repositories on different git systems.',
    long_description=long_description,
    long_description_content_type="text/markdown",
    author='Daniil Fedotov',
    author_email='fedotovdanil570@gmail.com',
    keywords='git, github, gitlab, label, labels, repository, api',
    url='https://github.com/fedotovdanil570/labelatory',
    packages=find_packages(),
    zip_safe=False
)