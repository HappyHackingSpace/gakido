package main

import (
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"strings"

	fhttp "github.com/bogdanfinn/fhttp"
	tls_client "github.com/bogdanfinn/tls-client"
	"github.com/bogdanfinn/tls-client/profiles"
)

// RequestSpec is the JSON contract Python sends to the native backend. Headers
// are an ordered list of [name, value] pairs so the exact on-the-wire header
// order is preserved; headerOrder, when set, overrides that order explicitly.
type RequestSpec struct {
	Method             string     `json:"method"`
	URL                string     `json:"url"`
	Headers            [][]string `json:"headers"`
	HeaderOrder        []string   `json:"header_order"`
	BodyB64            string     `json:"body_b64"`
	Profile            string     `json:"profile"`
	Proxy              string     `json:"proxy"`
	TimeoutSeconds     int        `json:"timeout_seconds"`
	InsecureSkipVerify bool       `json:"insecure_skip_verify"`
	ForceHTTP1         bool       `json:"force_http1"`
	FollowRedirects    bool       `json:"follow_redirects"`
}

// ResponseSpec is the JSON contract the native backend returns to Python.
type ResponseSpec struct {
	Status  int        `json:"status"`
	Headers [][]string `json:"headers"`
	BodyB64 string     `json:"body_b64"`
	Proto   string     `json:"proto"`
	Error   string     `json:"error"`
}

// resolveProfile maps a tls-client profile name (resolved on the Python side
// from the gakido profile's "tls_client_profile" field) to a ClientProfile.
// An unknown or empty name degrades to Chrome so a request still succeeds with
// a plausible browser fingerprint rather than failing outright.
func resolveProfile(name string) profiles.ClientProfile {
	if p, ok := profiles.MappedTLSClients[name]; ok {
		return p
	}
	return profiles.Chrome_120
}

func errorResponse(err error) string {
	b, _ := json.Marshal(ResponseSpec{Error: err.Error()})
	return string(b)
}

// handleRequest performs one request described by specJSON and returns a
// ResponseSpec encoded as JSON. It never panics out to the C boundary: every
// failure path is reported through ResponseSpec.Error.
func handleRequest(specJSON string) (result string) {
	defer func() {
		if r := recover(); r != nil {
			result = errorResponse(fmt.Errorf("native backend panic: %v", r))
		}
	}()

	var spec RequestSpec
	if err := json.Unmarshal([]byte(specJSON), &spec); err != nil {
		return errorResponse(fmt.Errorf("invalid request spec: %w", err))
	}

	timeout := spec.TimeoutSeconds
	if timeout <= 0 {
		timeout = 30
	}

	opts := []tls_client.HttpClientOption{
		tls_client.WithTimeoutSeconds(timeout),
		tls_client.WithClientProfile(resolveProfile(spec.Profile)),
	}
	if !spec.FollowRedirects {
		opts = append(opts, tls_client.WithNotFollowRedirects())
	}
	if spec.InsecureSkipVerify {
		opts = append(opts, tls_client.WithInsecureSkipVerify())
	}
	if spec.ForceHTTP1 {
		opts = append(opts, tls_client.WithForceHttp1())
	}
	if spec.Proxy != "" {
		opts = append(opts, tls_client.WithProxyUrl(spec.Proxy))
	}

	client, err := tls_client.NewHttpClient(tls_client.NewNoopLogger(), opts...)
	if err != nil {
		return errorResponse(fmt.Errorf("create client: %w", err))
	}
	defer client.CloseIdleConnections()

	var bodyReader io.Reader
	if spec.BodyB64 != "" {
		raw, err := base64.StdEncoding.DecodeString(spec.BodyB64)
		if err != nil {
			return errorResponse(fmt.Errorf("decode body: %w", err))
		}
		bodyReader = strings.NewReader(string(raw))
	}

	req, err := fhttp.NewRequest(strings.ToUpper(spec.Method), spec.URL, bodyReader)
	if err != nil {
		return errorResponse(fmt.Errorf("build request: %w", err))
	}

	applyHeaders(req, spec)

	resp, err := client.Do(req)
	if err != nil {
		return errorResponse(fmt.Errorf("request failed: %w", err))
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return errorResponse(fmt.Errorf("read response body: %w", err))
	}

	out := ResponseSpec{
		Status:  resp.StatusCode,
		Proto:   resp.Proto,
		BodyB64: base64.StdEncoding.EncodeToString(respBody),
		Headers: make([][]string, 0, len(resp.Header)),
	}
	for name, values := range resp.Header {
		for _, v := range values {
			out.Headers = append(out.Headers, []string{name, v})
		}
	}

	b, err := json.Marshal(out)
	if err != nil {
		return errorResponse(fmt.Errorf("encode response: %w", err))
	}
	return string(b)
}

// applyHeaders sets the request headers in the caller-supplied order and
// records that order so fhttp emits them in exactly that sequence (header order
// is itself a fingerprinting signal).
func applyHeaders(req *fhttp.Request, spec RequestSpec) {
	req.Header = fhttp.Header{}
	order := spec.HeaderOrder
	for _, pair := range spec.Headers {
		if len(pair) != 2 {
			continue
		}
		name, value := pair[0], pair[1]
		if strings.EqualFold(name, "host") {
			// fhttp derives :authority / Host from req.Host, not the map.
			req.Host = value
			continue
		}
		req.Header[name] = append(req.Header[name], value)
		if len(spec.HeaderOrder) == 0 {
			order = append(order, name)
		}
	}
	if len(order) > 0 {
		normalized := make([]string, 0, len(order))
		for _, name := range order {
			if !strings.EqualFold(name, "host") {
				normalized = append(normalized, name)
			}
		}
		req.Header[fhttp.HeaderOrderKey] = normalized
	}
}
