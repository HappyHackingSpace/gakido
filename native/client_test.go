package main

import (
	"encoding/base64"
	"encoding/json"
	"strings"
	"testing"
)

// TestHandleRequestChromeFingerprint is a live, network-dependent check that
// the native backend reproduces a real Chrome TLS + HTTP/2 fingerprint. It is
// skipped automatically when the network is unavailable.
func TestHandleRequestChromeFingerprint(t *testing.T) {
	spec := RequestSpec{
		Method:  "GET",
		URL:     "https://tls.peet.ws/api/all",
		Profile: "chrome_120",
		Headers: [][]string{
			{"User-Agent", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
			{"Accept", "*/*"},
		},
		TimeoutSeconds: 30,
	}
	in, _ := json.Marshal(spec)

	var resp ResponseSpec
	if err := json.Unmarshal([]byte(handleRequest(string(in))), &resp); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if resp.Error != "" {
		t.Skipf("skipping live test (backend error, likely no network): %s", resp.Error)
	}
	if resp.Status != 200 {
		t.Fatalf("expected 200, got %d", resp.Status)
	}
	if !strings.Contains(resp.Proto, "2") {
		t.Fatalf("expected HTTP/2, got %q", resp.Proto)
	}

	body, err := base64.StdEncoding.DecodeString(resp.BodyB64)
	if err != nil {
		t.Fatalf("decode body: %v", err)
	}
	var parsed struct {
		TLS struct {
			JA4 string `json:"ja4"`
		} `json:"tls"`
		HTTP2 struct {
			AkamaiFingerprint string `json:"akamai_fingerprint"`
		} `json:"http2"`
	}
	if err := json.Unmarshal(body, &parsed); err != nil {
		t.Fatalf("parse peet body: %v", err)
	}

	const wantJA4 = "t13d1516h2_8daaf6152771_02713d6af862"
	const wantAkamai = "1:65536;2:0;4:6291456;6:262144|15663105|0|m,a,s,p"
	if parsed.TLS.JA4 != wantJA4 {
		t.Errorf("JA4 mismatch:\n got %s\nwant %s", parsed.TLS.JA4, wantJA4)
	}
	if parsed.HTTP2.AkamaiFingerprint != wantAkamai {
		t.Errorf("Akamai fingerprint mismatch:\n got %s\nwant %s", parsed.HTTP2.AkamaiFingerprint, wantAkamai)
	}
}

func TestResolveProfileFallback(t *testing.T) {
	// Unknown names must not panic; they fall back to a Chrome profile.
	_ = resolveProfile("does_not_exist")
	_ = resolveProfile("")
}
