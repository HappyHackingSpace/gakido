#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <arpa/inet.h>
#include <netdb.h>
#include <netinet/in.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <sys/types.h>
#include <unistd.h>

// Simple helper to set a double timeout on a socket.
static int set_timeout(int fd, double timeout_seconds) {
    struct timeval tv;
    tv.tv_sec = (int)timeout_seconds;
    tv.tv_usec = (int)((timeout_seconds - tv.tv_sec) * 1000000);
    if (setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv)) < 0) {
        return -1;
    }
    if (setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof(tv)) < 0) {
        return -1;
    }
    return 0;
}

// Extend a bytearray in-place using PyByteArray_Concat (creates new object).
static int ba_extend(PyObject **ba, PyObject *chunk) {
    PyObject *new_ba = PyByteArray_Concat(*ba, chunk);
    if (!new_ba) {
        return -1;
    }
    Py_DECREF(*ba);
    *ba = new_ba;
    return 0;
}

static PyObject *native_request(PyObject *self, PyObject *args, PyObject *kwargs) {
    const char *method;
    const char *host;
    const char *path;
    PyObject *headers_obj;
    Py_buffer body = {0};
    int port;
    double timeout = 10.0;
    static char *kwlist[] = {"method", "host", "port", "path", "headers", "body", "timeout", NULL};

    if (!PyArg_ParseTupleAndKeywords(
            args,
            kwargs,
            "ssiss|y*d",
            kwlist,
            &method,
            &host,
            &port,
            &path,
            &headers_obj,
            &body,
            &timeout)) {
        return NULL;
    }

    PyObject *headers_seq = PySequence_Fast(headers_obj, "headers must be a sequence");
    if (!headers_seq) {
        PyBuffer_Release(&body);
        return NULL;
    }

    // Build request buffer.
    PyObject *req_buf = PyByteArray_FromStringAndSize(NULL, 0);
    if (!req_buf) {
        Py_DECREF(headers_seq);
        PyBuffer_Release(&body);
        return NULL;
    }

    PyObject *line = PyUnicode_FromFormat("%s %s HTTP/1.1\r\n", method, path);
    if (!line) {
        Py_DECREF(req_buf);
        Py_DECREF(headers_seq);
        PyBuffer_Release(&body);
        return NULL;
    }
    PyObject *line_bytes = PyUnicode_AsASCIIString(line);
    if (!line_bytes || ba_extend(&req_buf, line_bytes) < 0) {
        Py_XDECREF(line_bytes);
        Py_DECREF(line);
        Py_DECREF(req_buf);
        Py_DECREF(headers_seq);
        PyBuffer_Release(&body);
        return NULL;
    }
    Py_DECREF(line_bytes);
    Py_DECREF(line);

    // Track if user supplied Connection header.
    int has_connection = 0;

    Py_ssize_t len = PySequence_Fast_GET_SIZE(headers_seq);
    for (Py_ssize_t i = 0; i < len; i++) {
        PyObject *tuple = PySequence_Fast_GET_ITEM(headers_seq, i);
        PyObject *key = NULL;
        PyObject *val = NULL;
        if (!PyTuple_Check(tuple) || PyTuple_GET_SIZE(tuple) != 2) {
            PyErr_SetString(PyExc_TypeError, "header entries must be 2-tuples");
            Py_DECREF(req_buf);
            Py_DECREF(headers_seq);
            PyBuffer_Release(&body);
            return NULL;
        }
        key = PyTuple_GET_ITEM(tuple, 0);
        val = PyTuple_GET_ITEM(tuple, 1);
        PyObject *kbytes = PyUnicode_AsASCIIString(key);
        PyObject *vbytes = PyUnicode_AsASCIIString(val);
        if (!kbytes || !vbytes) {
            Py_XDECREF(kbytes);
            Py_XDECREF(vbytes);
            Py_DECREF(req_buf);
            Py_DECREF(headers_seq);
            PyBuffer_Release(&body);
            return NULL;
        }
        if (!has_connection && PyUnicode_Check(key)) {
            PyObject *lower = PyObject_CallMethod(key, "lower", NULL);
            if (lower) {
                if (PyUnicode_CompareWithASCIIString(lower, "connection") == 0) {
                    has_connection = 1;
                }
                Py_DECREF(lower);
            }
        }
        PyObject *header_line = PyUnicode_FromFormat("%U: %U\r\n", key, val);
        PyObject *header_bytes = PyUnicode_AsASCIIString(header_line);
        if (!header_bytes || ba_extend(&req_buf, header_bytes) < 0) {
            Py_XDECREF(header_bytes);
            Py_DECREF(header_line);
            Py_DECREF(req_buf);
            Py_DECREF(headers_seq);
            PyBuffer_Release(&body);
            return NULL;
        }
        Py_DECREF(header_line);
        Py_DECREF(header_bytes);
        Py_DECREF(kbytes);
        Py_DECREF(vbytes);
    }

    if (!has_connection) {
        PyObject *conn_bytes = PyBytes_FromString("Connection: close\r\n");
        if (!conn_bytes || ba_extend(&req_buf, conn_bytes) < 0) {
            Py_XDECREF(conn_bytes);
            Py_DECREF(req_buf);
            Py_DECREF(headers_seq);
            PyBuffer_Release(&body);
            return NULL;
        }
        Py_DECREF(conn_bytes);
    }

    PyObject *crlf = PyBytes_FromString("\r\n");
    if (!crlf || ba_extend(&req_buf, crlf) < 0) {
        Py_XDECREF(crlf);
        Py_DECREF(req_buf);
        Py_DECREF(headers_seq);
        PyBuffer_Release(&body);
        return NULL;
    }
    Py_DECREF(crlf);
    if (body.len > 0) {
        PyObject *body_bytes = PyBytes_FromStringAndSize(body.buf, body.len);
        if (!body_bytes || ba_extend(&req_buf, body_bytes) < 0) {
            Py_XDECREF(body_bytes);
            Py_DECREF(req_buf);
            Py_DECREF(headers_seq);
            PyBuffer_Release(&body);
            return NULL;
        }
        Py_DECREF(body_bytes);
    }

    // Resolve host.
    char port_str[16];
    snprintf(port_str, sizeof(port_str), "%d", port);
    struct addrinfo hints;
    struct addrinfo *res = NULL;
    memset(&hints, 0, sizeof(hints));
    hints.ai_family = AF_UNSPEC;
    hints.ai_socktype = SOCK_STREAM;

    int gai = getaddrinfo(host, port_str, &hints, &res);
    if (gai != 0) {
        PyErr_Format(PyExc_ConnectionError, "getaddrinfo failed: %s", gai_strerror(gai));
        Py_DECREF(req_buf);
        Py_DECREF(headers_seq);
        PyBuffer_Release(&body);
        return NULL;
    }

    int sockfd = -1;
    struct addrinfo *rp;
    for (rp = res; rp != NULL; rp = rp->ai_next) {
        sockfd = socket(rp->ai_family, rp->ai_socktype, rp->ai_protocol);
        if (sockfd == -1) {
            continue;
        }
        set_timeout(sockfd, timeout);
        if (connect(sockfd, rp->ai_addr, rp->ai_addrlen) == 0) {
            break;
        }
        close(sockfd);
        sockfd = -1;
    }
    freeaddrinfo(res);

    if (sockfd == -1) {
        PyErr_SetString(PyExc_ConnectionError, "failed to connect");
        Py_DECREF(req_buf);
        Py_DECREF(headers_seq);
        PyBuffer_Release(&body);
        return NULL;
    }

    // Send request.
    Py_ssize_t req_len = PyByteArray_GET_SIZE(req_buf);
    ssize_t sent = send(sockfd, PyByteArray_AS_STRING(req_buf), (size_t)req_len, 0);
    if (sent < req_len) {
        close(sockfd);
        PyErr_SetString(PyExc_ConnectionError, "failed to send full request");
        Py_DECREF(req_buf);
        Py_DECREF(headers_seq);
        PyBuffer_Release(&body);
        return NULL;
    }

    // Receive response into bytearray.
    PyObject *resp_buf = PyByteArray_FromStringAndSize(NULL, 0);
    if (!resp_buf) {
        close(sockfd);
        Py_DECREF(req_buf);
        Py_DECREF(headers_seq);
        PyBuffer_Release(&body);
        return NULL;
    }

    char recvbuf[4096];
    ssize_t n;
    while ((n = recv(sockfd, recvbuf, sizeof(recvbuf), 0)) > 0) {
        PyObject *chunk = PyBytes_FromStringAndSize(recvbuf, n);
        if (!chunk || ba_extend(&resp_buf, chunk) < 0) {
            Py_XDECREF(chunk);
            close(sockfd);
            Py_DECREF(resp_buf);
            Py_DECREF(req_buf);
            Py_DECREF(headers_seq);
            PyBuffer_Release(&body);
            return NULL;
        }
        Py_DECREF(chunk);
    }
    close(sockfd);

    // Parse response.
    char *resp_data = PyByteArray_AS_STRING(resp_buf);
    Py_ssize_t resp_size = PyByteArray_GET_SIZE(resp_buf);
    const char *marker = "\r\n\r\n";
    char *header_end = strstr(resp_data, marker);
    if (!header_end) {
        PyErr_SetString(PyExc_ValueError, "malformed HTTP response (no header terminator)");
        Py_DECREF(resp_buf);
        Py_DECREF(req_buf);
        Py_DECREF(headers_seq);
        PyBuffer_Release(&body);
        return NULL;
    }
    Py_ssize_t header_len = header_end - resp_data;
    Py_ssize_t body_offset = header_len + 4;
    Py_ssize_t body_len = resp_size - body_offset;

    // Parse status line.
    char *line_end = memchr(resp_data, '\n', resp_size);
    if (!line_end) {
        PyErr_SetString(PyExc_ValueError, "malformed status line");
        Py_DECREF(resp_buf);
        Py_DECREF(req_buf);
        Py_DECREF(headers_seq);
        PyBuffer_Release(&body);
        return NULL;
    }
    *line_end = '\0';
    int status = 0;
    char version[16] = {0};
    char reason[256] = {0};
    sscanf(resp_data, "HTTP/%15s %d %255[^\r\n]", version, &status, reason);

    // Parse headers.
    PyObject *py_headers = PyList_New(0);
    char *cursor = line_end + 1;
    while (cursor < resp_data + header_len) {
        char *line_break = memchr(cursor, '\n', (resp_data + header_len) - cursor);
        if (!line_break) {
            break;
        }
        *line_break = '\0';
        char *colon = strchr(cursor, ':');
        if (colon) {
            *colon = '\0';
            char *name = cursor;
            char *value = colon + 1;
            while (*value == ' ' || *value == '\t') {
                value++;
            }
            PyObject *py_name = PyUnicode_DecodeLatin1(name, strlen(name), NULL);
            PyObject *py_value = PyUnicode_DecodeLatin1(value, strlen(value), NULL);
            PyObject *tuple = PyTuple_Pack(2, py_name, py_value);
            PyList_Append(py_headers, tuple);
            Py_DECREF(tuple);
            Py_DECREF(py_name);
            Py_DECREF(py_value);
        }
        cursor = line_break + 1;
    }

    PyObject *py_body = PyBytes_FromStringAndSize(resp_data + body_offset, body_len);
    PyObject *py_reason = PyUnicode_DecodeLatin1(reason, strlen(reason), NULL);
    PyObject *py_version = PyUnicode_DecodeLatin1(version, strlen(version), NULL);

    PyObject *result = PyTuple_Pack(5, PyLong_FromLong(status), py_reason, py_version, py_headers, py_body);

    Py_DECREF(py_reason);
    Py_DECREF(py_version);
    Py_DECREF(py_headers);
    Py_DECREF(py_body);
    Py_DECREF(resp_buf);
    Py_DECREF(req_buf);
    Py_DECREF(headers_seq);
    PyBuffer_Release(&body);
    return result;
}

static PyMethodDef GakidoMethods[] = {
    {"request", (PyCFunction)native_request, METH_VARARGS | METH_KEYWORDS, "Perform an HTTP/1.1 request over TCP."},
    {NULL, NULL, 0, NULL}};

static struct PyModuleDef gakido_module = {
    PyModuleDef_HEAD_INIT,
    "gakido_core",
    "Native HTTP fast-path for Gakido.",
    -1,
    GakidoMethods,
};

PyMODINIT_FUNC PyInit_gakido_core(void) { return PyModule_Create(&gakido_module); }
