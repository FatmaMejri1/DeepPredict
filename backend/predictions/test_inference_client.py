import io
import json
import urllib.error
from unittest import TestCase, mock

from predictions import inference_client
from predictions.inference_client import InferenceError, NotEnoughHistory


class InferenceClientTests(TestCase):

    @mock.patch("predictions.inference_client.urllib.request.urlopen")
    @mock.patch("predictions.inference_client.INFERENCE_SERVICE_URL", "http://localhost:8001/")
    def test_successful_prediction(self, urlopen):
        expected = {"risk_score": 0.85, "risk_level": "HIGH"}

        response = urlopen.return_value.__enter__.return_value
        response.read.return_value = json.dumps(expected).encode("utf-8")

        result = inference_client.predict([{"smart_5_raw": 10}])

        self.assertEqual(result, expected)

        request = urlopen.call_args[0][0]
        self.assertEqual(request.full_url, "http://localhost:8001/predict")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(
            json.loads(request.data.decode("utf-8")),
            {"readings": [{"smart_5_raw": 10}]},
        )
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 30)

    def make_http_error(self, code, body):
        return urllib.error.HTTPError(
            url="http://localhost:8001/predict",
            code=code,
            msg="HTTP error",
            hdrs=None,
            fp=io.BytesIO(body.encode("utf-8")),
        )

    @mock.patch("predictions.inference_client.urllib.request.urlopen")
    def test_422_not_enough_history(self, urlopen):
        urlopen.side_effect = self.make_http_error(
            422,
            json.dumps({"detail": "Not enough valid history"}),
        )

        with self.assertRaises(NotEnoughHistory):
            inference_client.predict([])

    @mock.patch("predictions.inference_client.urllib.request.urlopen")
    def test_422_other_validation_error(self, urlopen):
        urlopen.side_effect = self.make_http_error(
            422,
            json.dumps({"detail": "Invalid readings"}),
        )

        with self.assertRaisesRegex(InferenceError, "Inference validation error"):
            inference_client.predict([])

    @mock.patch("predictions.inference_client.urllib.request.urlopen")
    def test_422_invalid_json_body(self, urlopen):
        urlopen.side_effect = self.make_http_error(422, "Invalid JSON body")

        with self.assertRaisesRegex(InferenceError, "Invalid JSON body"):
            inference_client.predict([])

    @mock.patch("predictions.inference_client.urllib.request.urlopen")
    def test_http_500_error(self, urlopen):
        urlopen.side_effect = self.make_http_error(500, "Internal server error")

        with self.assertRaisesRegex(InferenceError, "HTTP 500"):
            inference_client.predict([])

    @mock.patch("predictions.inference_client.urllib.request.urlopen")
    def test_connection_error(self, urlopen):
        urlopen.side_effect = urllib.error.URLError("Connection refused")

        with self.assertRaisesRegex(InferenceError, "Failed to connect"):
            inference_client.predict([])

    @mock.patch("predictions.inference_client.urllib.request.urlopen")
    def test_invalid_json_response(self, urlopen):
        response = urlopen.return_value.__enter__.return_value
        response.read.return_value = b"not a valid JSON"

        with self.assertRaisesRegex(InferenceError, "Inference error"):
            inference_client.predict([])

    @mock.patch("predictions.inference_client.urllib.request.urlopen")
    def test_unexpected_exception(self, urlopen):
        urlopen.side_effect = RuntimeError("Unexpected failure")

        with self.assertRaisesRegex(InferenceError, "Unexpected failure"):
            inference_client.predict([])
