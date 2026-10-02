package main

/*
#include <stdlib.h>
*/
import "C"

import "unsafe"

// GakidoRequest performs one HTTP request described by the JSON spec in `input`
// and returns a newly allocated C string holding the JSON ResponseSpec. The
// caller owns the returned pointer and must release it with GakidoFreeString.
//
//export GakidoRequest
func GakidoRequest(input *C.char) *C.char {
	return C.CString(handleRequest(C.GoString(input)))
}

// GakidoFreeString releases a string previously returned by GakidoRequest.
//
//export GakidoFreeString
func GakidoFreeString(p *C.char) {
	C.free(unsafe.Pointer(p))
}

// main is required for c-shared build mode but is never executed when the
// library is loaded from Python.
func main() {}
