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

        # Use pre-existing base install
        COPY {{ base_env_path }} /tmp/base-environment.frozen.yml
        RUN conda env update -p ${NB_PYTHON_PREFIX} -f /tmp/base-environment.frozen.yml

        # Allow target path repo is cloned to be configurable
        ARG REPO_DIR=${HOME}
        ENV REPO_DIR ${REPO_DIR}
        WORKDIR ${REPO_DIR}

        COPY --chown=${NB_UID} src/ ${REPO_DIR}

        USER ${NB_USER}

        COPY {{ activate_conda_path }} /etc/profile.d/activate-conda.sh

        # Add entrypoint
        COPY /repo2docker-entrypoint /usr/local/bin/repo2docker-entrypoint
        ENTRYPOINT ["/usr/local/bin/repo2docker-entrypoint"]


        ENV SHELL=/bin/bash
        # Specify the default command to run
        CMD ["jupyter", "notebook", "--ip", "0.0.0.0"]
    """

    def get_build_script_files(self):
        return {
           str(pathlib.Path(__file__).resolve().parent / "environment.yml"): "/tmp/base-environment.frozen.yml",
           str(pathlib.Path(__file__).resolve().parent / "entrypoint"): "/usr/local/bin/entrypoint",
           str(pathlib.Path(__file__).resolve().parent / "activate-conda.sh"): "/etc/profile.d/activate-conda.sh"
        }

    def render(self):
        t = jinja2.Template(self.TEMPLATE)

        return t.render(
            miniconda_version="4.7.12",
            base_env_path=self.generate_build_context_filename(str(pathlib.Path(__file__).resolve().parent / "environment.yml"))[0],
            entrypoint_path=self.generate_build_context_filename(str(pathlib.Path(__file__).resolve().parent / "entrypoint"))[0],
            activate_conda_path=self.generate_build_context_filename(str(pathlib.Path(__file__).resolve().parent / "activate-conda.sh"))[0],
        )