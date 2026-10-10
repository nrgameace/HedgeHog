from pathlib import Path

from app.settings import ENV_FILE, load_env

EXAMPLE_FILE = Path(__file__).resolve().parent.parent / ".env.example"

# Every variable the app reads from the environment, so the template cannot
# drift from the code and leave someone with a key in the wrong place.
DOCUMENTED_VARIABLES = (
    "MOCK_MODEL",
    "AKAMAI_API_BASE_URL",
    "AKAMAI_CHAT_MODEL",
    "AKAMAI_API_KEY",
)


def test_the_example_file_is_committed_for_people_to_copy():
    assert EXAMPLE_FILE.is_file()


def test_the_example_documents_every_variable_the_app_reads():
    example = EXAMPLE_FILE.read_text()

    for variable in DOCUMENTED_VARIABLES:
        assert f"{variable}=" in example, f"{variable} is read by the app but not in .env.example"


def test_the_example_carries_no_real_values():
    """The template is committed, so each key must be left blank or safely defaulted."""
    assignments = dict(
        line.split("=", 1)
        for line in EXAMPLE_FILE.read_text().splitlines()
        if "=" in line and not line.startswith("#")
    )

    assert assignments["AKAMAI_API_KEY"] == ""
    assert assignments["AKAMAI_API_BASE_URL"] == ""
    assert assignments["MOCK_MODEL"] == "true"


def test_a_missing_env_file_is_not_an_error(tmp_path):
    """Nothing should break for a teammate who has not created one."""
    assert load_env(tmp_path / "nonexistent.env") is False


def test_loads_values_from_a_file(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("HEDGEHOG_TEST_VARIABLE=from-file\n")

    assert load_env(env_file) is True

    import os

    assert os.environ["HEDGEHOG_TEST_VARIABLE"] == "from-file"
    del os.environ["HEDGEHOG_TEST_VARIABLE"]


def test_an_existing_variable_is_not_overridden(tmp_path, monkeypatch):
    """A real export or a deployment's injected config must win over the file."""
    monkeypatch.setenv("HEDGEHOG_TEST_VARIABLE", "from-environment")
    env_file = tmp_path / ".env"
    env_file.write_text("HEDGEHOG_TEST_VARIABLE=from-file\n")

    load_env(env_file)

    import os

    assert os.environ["HEDGEHOG_TEST_VARIABLE"] == "from-environment"


def test_the_env_file_sits_beside_requirements_so_the_path_is_predictable():
    assert ENV_FILE.name == ".env"
    assert (ENV_FILE.parent / "requirements.txt").is_file()
