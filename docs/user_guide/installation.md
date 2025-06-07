# Installation

This guide provides instructions for installing Grizabella in different ways, depending on your needs.

## As a Library

### Using pip (Future - Once Published)

Once Grizabella is published to the Python Package Index (PyPI), you will be able to install it easily using pip:

```bash
pip install grizabella
```

Stay tuned for updates on our official PyPI release!

### From Source (for Development or Current Use)

If you want to use the latest development version or contribute to Grizabella, you can install it from source:

1. **Clone the repository:**

    ```bash
    git clone https://github.com/pwilkin/grizabella.git
    cd grizabella
    ```

2. **Install using Poetry:**
    We use Poetry for dependency management and packaging. Ensure you have Poetry installed.

    ```bash
    poetry install
    ```

    This command will create a virtual environment (if one isn't active) and install all necessary dependencies.

## Standalone PySide6 Application

Grizabella includes a PySide6-based graphical user interface for managing your data.

### Running from Source

After installing from source using Poetry (see above), you can run the UI application with:

```bash
poetry run grizabella-ui
```

## System Dependencies

### Python Version

Grizabella requires **Python version >=3.10 and <3.14**. Please ensure you have a compatible Python version installed.

### Arrow C++ Libraries (for LanceDB)

The `lancedb` library, used by Grizabella for vector storage, depends on the Apache Arrow C++ libraries. You'll need to install these on your system if they are not already present.

* **For Debian/Ubuntu:**

    ```bash
    sudo apt update
    sudo apt install -y -V libarrow-dev
    # You might also need:
    # sudo apt install -y -V libarrow-python-dev
    ```

* **For macOS (using Homebrew):**

    ```bash
    brew install apache-arrow
    ```

* **For other systems or Conda:**
    Please refer to the official Apache Arrow installation guide: [https://arrow.apache.org/install/](https://arrow.apache.org/install/)

    If you are using Conda, you might be able to install Arrow via:

    ```bash
    conda install -c conda-forge pyarrow
    ```

    Ensure that the `pyarrow` version is compatible with `lancedb`.

## Verifying Installation

### Library

To verify that the Grizabella library is installed correctly, open a Python interpreter and try importing it:

```python
try:
    from grizabella.api import Grizabella
    print("Grizabella library imported successfully!")
except ImportError:
    print("Failed to import Grizabella library.")
```

### PySide6 UI

Launch the UI as described above:

```bash
poetry run grizabella-ui
```

If the application window appears, the UI component is likely installed correctly. You can try connecting to a database (or creating a new one) to further verify.
