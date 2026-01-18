class ExtraFingerprints:
    """
    Placeholder container for additional fingerprint material. This is not yet
    fully integrated into the TLS handshake but is stored for future native
    ClientHello work.
    """

    def __init__(
        self,
        alpn: list[str] | None = None,
        ciphers: list[str] | None = None,
        curves: list[str] | None = None,
        sig_algs: list[str] | None = None,
        extensions: list[str] | None = None,
    ) -> None:
        self.alpn = alpn or []
        self.ciphers = ciphers or []
        self.curves = curves or []
        self.sig_algs = sig_algs or []
        self.extensions = extensions or []
