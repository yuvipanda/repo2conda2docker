"""
Subset of repo2docker functionality focused on primarily Python projects.

Supports the following files from repo2docker:

1. environment.yml
2. requirements.txt
3. runtime.txt
4. postBuild
5. start

We try to re-use code from repo2docker wherever possible
"""
from traitlets.config import LoggingConfigurable, Application
from traitlets import Unicode
import pathlib
import jinja2
from repo2docker.buildpacks import BuildPack


class PrimaryPythonBuildPack(BuildPack):
    miniconda_version = Unicode(
        "4.7.12",
        help="""
        Version of miniconda to use as a base.

        Currently, this is the tag of the continuumio/miniconda3 base image
        """,
        config=True
    )

    TEMPLATE = """
        FROM continuumio/miniconda3:{{ miniconda_version }}

        # Let's try emulate the environment vars to repo2docker as much as we can
        # CONDA_DIR is ${APP_BASE}/conda in repo2docker, but we already have it in /opt/conda here
        ENV CONDA_DIR=/opt/conda
        ENV APP_BASE=/srv
        # We use the base existing conda env as our notebook env
        ENV NB_PYTHON_PREFIX=${CONDA_DIR}

        # Set up PATH
        ENV PATH=${NB_PYTHON_PREFIX}/bin:${PATH}
        # Set up shell to be bash
        ENV SHELL=/bin/bash

        # Set up user
        ARG NB_USER
        ARG NB_UID
        ENV USER ${NB_USER}
        ENV HOME /home/${NB_USER}

        RUN groupadd \
                --gid ${NB_UID} \
                ${NB_USER} && \
            useradd \
                --comment "Default user" \
                --create-home \
                --gid ${NB_UID} \
                --no-log-init \
                --shell /bin/bash \
                --uid ${NB_UID} \
                ${NB_USER}

        # FIXME: add apt.txt support here

        {% if build_script_files -%}
        # If scripts required during build are present, copy them
        {% for src, dst in build_script_files|dictsort %}
        COPY {{ src }} {{ dst }}
        {% endfor -%}
        {% endif -%}

        # Use pre-existing base install
        RUN conda env update -p ${NB_PYTHON_PREFIX} -f /tmp/base-environment.frozen.yml

        # Allow target path repo is cloned to be configurable
        ARG REPO_DIR=${HOME}
        ENV REPO_DIR ${REPO_DIR}
        WORKDIR ${REPO_DIR}

        COPY --chown=${NB_UID} src/ ${REPO_DIR}

        USER ${NB_USER}

        # Add entrypoint
        ENTRYPOINT ["/usr/local/bin/repo2docker-entrypoint"]

        # Specify the default command to run
        CMD ["jupyter", "notebook", "--ip", "0.0.0.0"]
    """

    def get_build_script_files(self):
        return {
           str(pathlib.Path(__file__).resolve().parent / "environment.yml"): "/tmp/base-environment.frozen.yml",
           str(pathlib.Path(__file__).resolve().parent / "entrypoint"): "/usr/local/bin/repo2docker-entrypoint",
           str(pathlib.Path(__file__).resolve().parent / "activate-conda.sh"): "/etc/profile.d/activate-conda.sh"
        }

    def render(self):
        t = jinja2.Template(self.TEMPLATE)

        # Based on a physical location of a build script on the host,
        # create a mapping between:
        #   1. Location of a build script in a Docker build context
        #      ('assemble_files/<escaped-file-path-truncated>-<6-chars-of-its-hash>')
        #   2. Location of the aforemention script in the Docker image
        # Base template basically does: COPY <1.> <2.>
        build_script_files = {
            self.generate_build_context_filename(k)[0]: v
            for k, v in self.get_build_script_files().items()
        }

        template = t.render(
            miniconda_version="4.7.12",
            build_script_files=build_script_files
        )
        self.log.debug("Generated template...")
        self.log.debug(template)
        return template