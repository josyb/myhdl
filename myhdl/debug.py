import platform

from myhdl import __version__


def print_versions():
    versions = [
        ("myhdl", __version__),
        ("Python Version", platform.python_version()),
        ("Python Implementation", platform.python_implementation()),
        ("OS", platform.platform()),
    ]

    print()
    print("INSTALLED VERSIONS")
    print("------------------")
    for k, v in versions:
        print(f"{k}: {v}")


if __name__ == "__main__":
    print_versions()
