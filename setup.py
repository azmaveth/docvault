from setuptools import setup, find_packages

setup(
    name="docvault",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "click>=8.1.3",
        "rich>=13.3.1",
        "python-dotenv>=1.0.0",
        "requests>=2.28.1",
        "beautifulsoup4>=4.11.1",
        "html2text>=2020.1.16",
        "aiohttp>=3.8.4",
        "numpy>=1.24.0",
        "mcp-sdk>=0.1.0"
    ],
    entry_points={
        'console_scripts': [
            'dv=docvault.main:main',
        ],
    },
)
