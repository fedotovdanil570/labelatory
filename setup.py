from setuptools import setup, find_packages

with open('README.md', 'r') as f:
    # long_description = ''.join(f.readlines())
    long_description = ''
    lines = f.readlines()
    readme = []
    for line in lines:
        # if not line.startswith(('## Passed', '### Package', '<p>', '</p>', '<img')):
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
    package_data={
        'labelatory': ['templates/*.html'],
    },
    install_requires=['aiohttp', 'requests', 'Flask'],
    tests_require=[
        'pytest',
        'flexmock',
    ],
    entry_points={
        'console_scripts': [
            'labelatory = labelatory.labelatory:create_app',
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Environment :: Web Environment",
        "Framework :: Flask",
        "Programming Language :: Python :: Implementation",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Topic :: Software Development"
    ],
    zip_safe=False
)