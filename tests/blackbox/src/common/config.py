from dotenv import load_dotenv

from common.utils import get_env

load_dotenv()

DEFAULT_RETRY_WAIT_TIME = 60
DEFAULT_RETRY_MAX_WAIT_TIME = 600


class Config:
    """
    Config represent the test configurations.
    """

    test_data_path: str  # Path to the test data directory e.g. "~kyma-companion/tests/blackbox/data"
    namespace_scoped_test_data_path: str
    companion_api_url: str
    companion_token: (
        str  # Authentication token when the companion is deployed in MPS cluster.
    )
    test_cluster_url: str  # Gardener test cluster API server URL.
    test_cluster_ca_data: str  # Gardener test cluster CA data.
    test_cluster_auth_token: str  # Gardener test cluster authentication token.
    aicore_deployment_id_gpt4_mini: str
    aicore_configuration_id_gpt4_mini: str
    model_name: str
    model_temperature: int
    # Number of times to get the companion response for the same scenario to check if the response is consistent.
    iterations: int
    streaming_response_timeout: int
    max_workers: int
    retry_wait_time: int
    retry_max_wait_time: int

    def __init__(self) -> None:
        self.test_data_path = get_env("TEST_DATA_PATH", False, "./data")
        self.namespace_scoped_test_data_path = f"{self.test_data_path}/namespace-scoped"

        self.companion_api_url = get_env("COMPANION_API_URL")
        self.companion_token = get_env("COMPANION_TOKEN", False, "not-needed")
        self.test_cluster_url = get_env("TEST_CLUSTER_URL")
        self.test_cluster_ca_data = get_env("TEST_CLUSTER_CA_DATA")
        self.test_cluster_auth_token = get_env("TEST_CLUSTER_AUTH_TOKEN")
        self.aicore_deployment_id_gpt4_mini = get_env("AICORE_DEPLOYMENT_ID_GPT4_MINI")
        self.aicore_configuration_id_gpt4_mini = get_env(
            "AICORE_CONFIGURATION_ID_GPT4_MINI"
        )
        self.model_name = get_env("MODEL_NAME", False, "gpt4.o-mini")
        self.model_temperature = 0
        self.iterations = 3
        self.streaming_response_timeout = 10 * 60  # seconds
        self.max_workers = 1
        self.retry_wait_time = int(
            get_env("RETRY_WAIT_TIME", False, DEFAULT_RETRY_WAIT_TIME)
        )  # seconds
        self.retry_max_wait_time = int(
            get_env("RETRY_MAX_WAIT_TIME", False, DEFAULT_RETRY_MAX_WAIT_TIME)
        )  # seconds
