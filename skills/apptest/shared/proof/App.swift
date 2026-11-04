import SwiftUI

func flag(_ f: String) -> Bool { ProcessInfo.processInfo.arguments.contains(f) }

final class Store: ObservableObject {
    @Published var rows: [String] = []
    @Published var saving = false
    private var file: URL { FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0].appendingPathComponent("rows.json") }
    init() {
        if flag("-reset") { try? FileManager.default.removeItem(at: file) }
        if let d = try? Data(contentsOf: file), let r = try? JSONDecoder().decode([String].self, from: d) { rows = r }
    }
    func save() {
        if !flag("-bug-double") {
            guard !saving else { return }
        }
        saving = true
        let delay = flag("-slow-writes") ? 1.0 : 0.0
        DispatchQueue.main.asyncAfter(deadline: .now() + delay) {
            self.rows.append("Record \(self.rows.count + 1)")
            if let d = try? JSONEncoder().encode(self.rows) { try? d.write(to: self.file, options: .atomic) }
            self.saving = false
        }
    }
}

final class Net: ObservableObject {
    @Published var status = "-"
    func fetch() {
        let base = UserDefaults.standard.string(forKey: "baseURL") ?? "http://127.0.0.1:8897"
        let session: URLSession
        if let code = UserDefaults.standard.string(forKey: "chaos"), let c = Int(code) {
            ChaosProtocol.state.fault = .status(c); session = chaosSession()
        } else if flag("-chaos-offline") {
            ChaosProtocol.state.fault = .offline; session = chaosSession()
        } else if flag("-chaos-garbage") {
            ChaosProtocol.state.fault = .garbage; session = chaosSession()
        } else {
            let c = URLSessionConfiguration.ephemeral; c.timeoutIntervalForRequest = 3; session = URLSession(configuration: c)
        }
        status = "loading"
        session.dataTask(with: URL(string: base + "/ping")!) { data, resp, err in
            DispatchQueue.main.async {
                if let err = err as? URLError { self.status = "network error \(err.code.rawValue)"; return }
                let code = (resp as? HTTPURLResponse)?.statusCode ?? 0
                if code != 200 { self.status = "HTTP \(code)"; return }
                let ok = (data.flatMap { try? JSONSerialization.jsonObject(with: $0) }) != nil
                self.status = ok ? "HTTP 200 ok" : "corrupt response"
            }
        }.resume()
    }
}

struct ContentView: View {
    @StateObject var store = Store()
    @StateObject var net = Net()
    var body: some View {
        NavigationStack {
            List {
                Section {
                    Button("Save") { store.save() }.accessibilityIdentifier("save")
                    Button("Fetch data") { net.fetch() }.accessibilityIdentifier("fetch")
                    Text(net.status).accessibilityIdentifier("net-status")
                    NavigationLink("Details") { Text("Details page").navigationTitle("Details") }
                    if flag("-bug-crash") { Button("Report") { fatalError("planned crash") } }
                    if flag("-bug-a11y") { Button { } label: { Color.red.frame(width: 44, height: 44) }.accessibilityIdentifier("unlabeled") }
                }
                Section("Records") {
                    ForEach(store.rows, id: \.self) { Text($0).accessibilityIdentifier("order-row") }
                }
            }
            .navigationTitle("Proof")
        }
    }
}

@main struct ProofApp: App { var body: some Scene { WindowGroup { ContentView() } } }
