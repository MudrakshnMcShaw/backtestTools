import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="backtestTools",
    version="4.0.3",
    author="Mudraksh",
    author_email="contact.mudraksh@gmail.com",
    description="BacktestTools",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/MudrakshnMcShaw/backtestTools",
    project_urls={
        "Bug Tracker":
        "https://github.com/MudrakshnMcShaw/backtestTools/issues"
    },
    install_requires=["pymongo", "pandas", "numpy"],
    packages=["backtestTools"],
)
