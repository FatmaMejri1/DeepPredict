"""
DeepPredict Security Headers Middleware.
Addresses OWASP ZAP DAST recommendations:
- Content-Security-Policy (CSP)
- X-Content-Type-Options: nosniff
- Server banner version disclosure minimization
"""


class SecurityHeadersMiddleware:
    """
    Enforces security headers across all HTTP responses.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # 1. Content-Security-Policy
        if "Content-Security-Policy" not in response:
            response["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; "
                "font-src 'self'; "
                "connect-src 'self'; "
                "frame-ancestors 'none'; "
                "form-action 'self'; "
                "base-uri 'self'; "
                "object-src 'none'"
            )

        # 2. Anti-MIME-sniffing
        response["X-Content-Type-Options"] = "nosniff"

        # 3. Mask server version banner
        response["Server"] = "DeepPredict"

        return response
