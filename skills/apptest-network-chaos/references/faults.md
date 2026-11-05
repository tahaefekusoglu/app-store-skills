# network-chaos — scenarios, injection paths, templates

## Where to inject (cheap to expensive)

1. **Unit / component-level mock:** a test version of the app's network client
   (MockClient, URLProtocol, msw, fake HttpMessageHandler) returns an error or delay.
   Fastest and most precise; measures UI text and data state directly.
2. **Proxy (`scripts/nc_proxy.py`):** if the base URL can change in tests (NC-11), the
   app is pointed at `http://localhost:<port>`; the proxy forwards to a MOCK / STAGING
   server and injects faults into requests matching a rule. Real app, real client code,
   on a temporary simulator.
3. **By hand:** if the base URL cannot change and there is no mock (below).

Verification status (2026-11-03): the proxy ran in its own self-test and with curl
against a real HTTPS server; not yet tried with a real iOS app. The Swift mock
compiled, not run.

NEVER against a production server (NC-P1): the proxy does not run against a server whose
name does not look like mock / staging without `--confirm-nonprod`.

iOS detail (Apple, NSAllowsLocalNetworking): iOS 10–16 allows plain connections to
unqualified names (`localhost`), `.local` names and IP addresses; **since iOS 17, IP
addresses (127.0.0.1) are blocked by default**. Connect to the proxy with
`http://localhost:<port>`. If blocked, use `NSAllowsLocalNetworking` in the TEST build
only (do not put it in the release build — store-readiness).
https://developer.apple.com/documentation/bundleresources/information-property-list/nsapptransportsecurity/nsallowslocalnetworking

## Scenarios

| Id | State | Proxy rule | In a mock | Look at |
|---|---|---|---|---|
| NC-S1 | No network | — (no proxy: base URL on a closed port → "could not connect") | `notConnectedToInternet` / `SocketException` | clear message, cache / offline view (the app's decision), no crash |
| NC-S2 | Slow network | `delay:5000`, `slow:2000` | delayed response | loading indicator; UI does not freeze; cancel / back works |
| NC-S3 | Hanging connection / timeout | `hang:120` | request that never returns | NO endless spinner: error + retry in reasonable time (NC-12) |
| NC-S4 | Server error | `status:500`, `status:503` | 5xx | clear message, no data loss, retry |
| NC-S5 | Bad / partial response | `garbage`, `truncate:50` | invalid JSON | no crash; parse error does not reach the user as technical text |
| NC-S6 | Session lost | `status:401` (on authenticated paths) | 401 | re-login path; unfinished work / draft kept; no loop (401 → refresh → 401 …) |
| NC-S7 | Rate limit | `status:429` | 429 | retry is not immediate and not endless |
| NC-S8 | Temporary error, then recovery | `status:503@1` (first request only) | first call errors | automatic or manual retry produces ONE record (rapid-input RI-S9) |
| NC-S9 | Drop during a write | `^POST /…` → `drop` or `reset` | connection error on the write request | local state and server consistent; user was not told "saved"; no double record on retry |

Rule text matches "METHOD /path?query":

```sh
python3 -I <skills>/apptest-network-chaos/scripts/nc_proxy.py \
  --upstream https://staging.api.example.com --port 8899 --log ~/.cache/apptest/<key>/nc.jsonl \
  --rule '^POST /v1/orders' 'drop@1' \
  --rule '^GET /v1/feed' 'delay:4000' \
  --rule '^GET /v1/me' 'status:401'
```

The proxy runs in the background and is stopped by PID (CONVENTIONS §5.3; not
`pkill -f`). The log records which fault each request got (T5: reproduction).

Findings:

| Id | What | Severity |
|---|---|---|
| NC-20 | Crash / uncaught error on a network fault | USER BUG (2.1 if on launch — principle 7) |
| NC-21 | Endless spinner: no timeout, no retry (NC-S3) | USER BUG |
| NC-22 | Data loss: content the user entered is gone after a write error (NC-S9) | USER BUG |
| NC-23 | False "saved": a write that never reached the server shown as successful | USER BUG |
| NC-24 | Double record on retry (NC-S8, S9) | USER BUG (same finding as rapid-input RI-24: once) |
| NC-25 | Raw / technical error text (NSURLErrorDomain, stack trace, English system text in a non-English UI) | SUGGESTION (evidence for the NC-14 static candidate) |
| NC-26 | Loop or dead end when the session drops (NC-S6) | USER BUG |
| NC-27 | Does not recover by itself when the network returns (needs reopening) | SUGGESTION |

A crash / blank screen with no connection can also be seen in App Store review
(review network and IPv6-only network — network NW-12, rule 2.1); so NC-S1 and NC-S3 at
least once before release.

## Flutter (package:http / dio)

```dart
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

final failing = MockClient((req) async => throw http.ClientException('Connection reset'));
final slow = MockClient((req) async {
  await Future<void>.delayed(const Duration(seconds: 5));
  return http.Response('{"ok":true}', 200);
});
final serverError = MockClient((req) async => http.Response('{"error":"x"}', 503));
final garbage = MockClient((req) async => http.Response('{"data": [1,,', 200));
var calls = 0;
final flaky = MockClient((req) async => ++calls == 1 ? http.Response('', 503) : http.Response('{"id":1}', 201));
// Passed in place of the client via the app's dependency override path (e.g. Riverpod override);
// verify the text in the UI and the record count in the data (flaky → 1 record).
```

dio: `http_mock_adapter` (`DioAdapter`) with `onGet(...).reply(503, …)`,
`throws(…, DioException.connectionTimeout(…))`.

## Swift (URLProtocol — URLSession, Alamofire)

```swift
import Foundation

final class ChaosProtocol: URLProtocol {
    enum Fault { case offline, delay(TimeInterval), status(Int), garbage }
    /// Locked box: compiles in Swift 5 and Swift 6 (strict concurrency) mode.
    final class Box: @unchecked Sendable {
        private let lock = NSLock()
        private var value: Fault = .offline
        var fault: Fault {
            get { lock.lock(); defer { lock.unlock() }; return value }
            set { lock.lock(); value = newValue; lock.unlock() }
        }
    }
    static let state = Box()          // in a test: ChaosProtocol.state.fault = .status(503)

    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }

    override func startLoading() {
        switch Self.state.fault {
        case .offline:
            client?.urlProtocol(self, didFailWithError: URLError(.notConnectedToInternet))
        case .delay(let s):
            DispatchQueue.global().asyncAfter(deadline: .now() + s) { self.respond(200, Data("{}".utf8)) }
        case .status(let code):
            respond(code, Data("{\"error\":\"injected\"}".utf8))
        case .garbage:
            respond(200, Data("{\"data\": [1,,".utf8))
        }
    }
    override func stopLoading() {}

    private func respond(_ code: Int, _ body: Data) {
        let r = HTTPURLResponse(url: request.url!, statusCode: code, httpVersion: "HTTP/1.1",
                                headerFields: ["Content-Type": "application/json"])!
        client?.urlProtocol(self, didReceive: r, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: body)
        client?.urlProtocolDidFinishLoading(self)
    }
}

// In a test: give it to the session the app uses
func chaosSession() -> URLSession {
    let config = URLSessionConfiguration.ephemeral
    config.protocolClasses = [ChaosProtocol.self]
    return URLSession(configuration: config)
}
```

If `URLSession.shared` is used directly, use `URLProtocol.registerClass`; on a client
with a custom `URLSessionConfiguration`, `protocolClasses` must be given to that
configuration.

## TypeScript / React Native (msw)

```ts
import { http, HttpResponse, delay } from 'msw';
import { setupServer } from 'msw/node';

const server = setupServer(
  http.get('*/v1/feed', async () => { await delay(5000); return HttpResponse.json([]); }),
  http.post('*/v1/orders', () => HttpResponse.error()),            // network error
  http.get('*/v1/me', () => new HttpResponse(null, { status: 401 })),
);
beforeAll(() => server.listen()); afterAll(() => server.close());
```

## C# / .NET MAUI

```csharp
class ChaosHandler : HttpMessageHandler {
    public Func<HttpRequestMessage, Task<HttpResponseMessage>> Respond = _ =>
        throw new HttpRequestException("offline");
    protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage r, CancellationToken ct) => Respond(r);
}
// var client = new HttpClient(new ChaosHandler { Respond = _ => Task.FromResult(new HttpResponseMessage(HttpStatusCode.ServiceUnavailable)) });
```

## By hand (base URL cannot change, no mock)

In this case the agent cannot change the network (the Mac's network is not touched, T4).
These manual steps are suggested to the user, who does them:
- On a real device, Airplane mode / Wi-Fi off (NC-S1).
- On the Mac, Network Link Conditioner (Xcode Additional Tools) with "100% Loss" / "Very
  Bad Network" — the simulator uses the Mac's network; it MUST BE TURNED OFF when done
  (it affects the user's other work).
- For the next version: making the base URL changeable in the test build (NC-11) is
  suggested once.
