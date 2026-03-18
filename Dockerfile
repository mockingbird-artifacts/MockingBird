FROM ubuntu:22.04

RUN apt-get update && apt-get install -y \
    python3.11 \
    python3-pip \
    git \
    wget \
    curl \
    zip \
    unzip \
    rsync \
    vim \
    && rm -rf /var/lib/apt/lists/*

RUN arch=$(uname -m) && \
    if [ "$arch" = "x86_64" ]; then \
    MINICONDA_URL="https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh"; \
    elif [ "$arch" = "aarch64" ]; then \
    MINICONDA_URL="https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-aarch64.sh"; \
    else \
    echo "Unsupported architecture: $arch"; \
    exit 1; \
    fi && \
    wget $MINICONDA_URL -O miniconda.sh && \
    mkdir -p /root/.conda && \
    bash miniconda.sh -b -p /root/miniconda3 && \
    rm -f miniconda.sh

ENV PATH="/root/miniconda3/bin:${PATH}"

RUN pip3 install --upgrade pip

WORKDIR /home

RUN wget https://archive.apache.org/dist/maven/maven-3/3.9.9/binaries/apache-maven-3.9.9-bin.tar.gz
RUN tar xzvf apache-maven-3.9.9-bin.tar.gz
ENV PATH="/home/apache-maven-3.9.9/bin:${PATH}"
RUN rm apache-maven-3.9.9-bin.tar.gz

RUN mkdir -p tmp
WORKDIR /home/tmp
RUN git clone https://github.com/mockingbird-artifacts/MockingBird.git


WORKDIR /home/tmp/MockingBird

SHELL ["/bin/bash", "-c"]

RUN conda init bash

RUN echo "source /root/.bashrc && conda activate mockingbird" > /etc/profile.d/conda.sh && \
    echo "conda activate mockingbird" >> ~/.bashrc

RUN conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main && \
    conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r && \
    conda env create -f environment.yaml

RUN curl -s "https://get.sdkman.io" | bash && \
    bash -c "source /root/.sdkman/bin/sdkman-init.sh && \
        sdk install java 8.0.432-kona && \
        sdk install java 11.0.26-amzn && \
        sdk install java 21.0.3-graal && \
        sdk default java 8.0.432-kona"
        
ENV JAVA_HOME="/root/.sdkman/candidates/java/current"
ENV PATH="$JAVA_HOME/bin:$PATH"

RUN curl -fsSL https://ollama.com/install.sh | bash

RUN bash scripts/install_graal.sh

RUN mkdir -p /home/tmp/MockingBird/misc/sitter-libs
RUN git clone https://github.com/tree-sitter/tree-sitter-java.git /home/tmp/MockingBird/misc/sitter-libs/java && \
    cd /home/tmp/MockingBird/misc/sitter-libs/java && git checkout v0.23.5
RUN git clone https://github.com/tree-sitter/tree-sitter-python.git /home/tmp/MockingBird/misc/sitter-libs/python && \
    cd /home/tmp/MockingBird/misc/sitter-libs/python && git checkout v0.23.5

RUN mkdir -p /home/tmp/MockingBird/misc/java-callgraph
RUN git clone https://github.com/gousiosg/java-callgraph.git /home/tmp/MockingBird/misc/java-callgraph
WORKDIR /home/tmp/MockingBird/misc/java-callgraph
RUN mvn clean install -DskipTests

WORKDIR /home/tmp/MockingBird/misc
RUN wget https://github.com/EvoSuite/evosuite/releases/download/v1.2.0/evosuite-standalone-runtime-1.2.0.jar

WORKDIR /home/tmp/MockingBird

RUN bash scripts/download_original_projects.sh

RUN bash scripts/build_java_projects.sh

SHELL ["/bin/bash", "-c"]
RUN source /root/miniconda3/etc/profile.d/conda.sh && \
    conda activate MockingBird && \
    python src/crawler/crawl_java_package.py
