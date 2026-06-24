# Mocking Pipeline

## Introduction
The **Mocking Pipeline** facilitates automatic method call interception and serialization in Java, along with corresponding mocking and test generation in Python.

### Components:
- **CustomToStringConverter.java**: Serializes Java objects.
- **LoggingAspect.java**: Dynamically intercepts method calls and records I/O and side effects.
- **script.py**: Sets up mocking for Python.
- **log_parser.py**: Parses logs from Java execution.
- **mock_helper.py**: Handles deserialization in Python.
- **commons-fileupload**: A clean, reduced Java FileUpload project.
- **commons-fileupload-python**: The manually verified, translated Python FileUpload project.

## Setup Instructions

### Step 1: Prepare the Java Project
```bash
cp modify_pom.py commons-fileupload
cp add_java_files.py commons-fileupload
cd commons-fileupload
python3 modify_pom.py  # Modify pom.xml to add AspectJ, JSON, and other dependencies
python3 add_java_files.py  # Add Java source files to handle method interception
```

### Step 2:Build and Generate Logs
```bash
export JAVA_HOME=`/usr/libexec/java_home -v 1.8` # Or other command to switch to Java 8, as it allows easier inspection of internal fields for APIs like java.io
mvn clean install -Drat.skip  # Logs will be automatically generated
cp *.log ../commons-fileupload-python  # Copy logs to Python project
```

### Step 3: Set Up the Python Mocking Pipeline
```bash
cd ..
cp mock_helper.py commons-fileupload-python
cp log_parser.py commons-fileupload-python
cp script.py commons-fileupload-python
cd commons-fileupload-python
```

### Step 4: Run Mocking and Tests
```bash
for log_file in *.log; do python3 script.py "$log_file"; done
```
This generates test files named like: `{test_class_name}_{test_method_name}_decomposed_mocker_{index}_['{focal_method_class_name}', '{focal_method_name}'].py
Each test file invokes only one specific call to focal_method_name, replacing all other method calls with mocks.
Finally, run those mocked tests using:
```bash
PYTHONPATH=. python3 -m pytest -k mocker  # change the filter to validate specific methods
```
