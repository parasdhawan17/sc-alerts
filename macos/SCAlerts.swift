import SwiftUI
import AppKit
import UniformTypeIdentifiers

private let defaultSheet = "1fD1qL3GjtEanxnL0MvwByauKz3xe2MthMndNL3E14cg"

struct Preferences: Codable {
    var spreadsheetID = defaultSheet
}

struct SyncEvent: Decodable {
    let stage: String
    let message: String
    let count: Int?
    let processed: Int?
    let total: Int?
}

@MainActor
final class SyncModel: ObservableObject {
    @Published var month = Calendar.current.component(.month, from: Date())
    @Published var year = Calendar.current.component(.year, from: Date())
    @Published var spreadsheetID = defaultSheet
    @Published var configured = false
    @Published var running = false
    @Published var message = "Ready when you are."
    @Published var stage = "ready"
    @Published var progress: Double?
    @Published var completedAt: Date?
    @Published var settingsError: String?
    @Published var showSettings = false
    private var process: Process?
    let configDirectory = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0].appendingPathComponent("SC Alerts", isDirectory: true)

    var monthTitle: String { "\(Calendar.current.monthSymbols[month - 1]) \(year)" }
    var credentialsURL: URL { configDirectory.appendingPathComponent("credentials.json") }
    var preferencesURL: URL { configDirectory.appendingPathComponent("preferences.json") }
    var validSheet: Bool {
        !spreadsheetID.isEmpty && spreadsheetID.range(of: "^[A-Za-z0-9_-]+$", options: .regularExpression) != nil
    }

    init() {
        if let data = try? Data(contentsOf: preferencesURL), let prefs = try? JSONDecoder().decode(Preferences.self, from: data) {
            spreadsheetID = prefs.spreadsheetID
        }
        configured = FileManager.default.fileExists(atPath: credentialsURL.path)
        if !configured { message = "Connect Google to get started." }
    }

    func saveSettings() {
        guard validSheet else { settingsError = "Enter the spreadsheet ID from its Google Sheets URL."; return }
        do {
            try FileManager.default.createDirectory(at: configDirectory, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
            try JSONEncoder().encode(Preferences(spreadsheetID: spreadsheetID)).write(to: preferencesURL, options: .atomic)
            settingsError = nil
            showSettings = false
        } catch { settingsError = "Could not save settings. Check access to Application Support." }
    }

    func importCredentials() {
        let panel = NSOpenPanel()
        panel.allowedContentTypes = [.json]
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = false
        guard panel.runModal() == .OK, let url = panel.url else { return }
        do {
            let data = try Data(contentsOf: url)
            let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]
            guard let installed = json?["installed"] as? [String: Any],
                  let id = installed["client_id"] as? String, !id.isEmpty,
                  let secret = installed["client_secret"] as? String, !secret.isEmpty,
                  installed["auth_uri"] is String, installed["token_uri"] is String else {
                settingsError = "Choose OAuth credentials for a Google Desktop app."; return
            }
            try FileManager.default.createDirectory(at: configDirectory, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
            try data.write(to: credentialsURL, options: .atomic)
            try FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: credentialsURL.path)
            let token = configDirectory.appendingPathComponent("token.json")
            if FileManager.default.fileExists(atPath: token.path) { try FileManager.default.removeItem(at: token) }
            configured = true
            settingsError = nil
        } catch { settingsError = "Could not import that file. Choose valid Google Desktop OAuth credentials." }
    }

    func sync() {
        guard !running else { return }
        guard configured, validSheet else { showSettings = true; return }
        let worker = Bundle.main.bundleURL.appendingPathComponent("Contents/Resources/backend/sc-alerts-worker")
        guard FileManager.default.isExecutableFile(atPath: worker.path) else {
            stage = "error"; message = "The bundled sync worker is missing. Rebuild or reinstall SC Alerts."; return
        }
        let task = Process()
        let output = Pipe()
        task.executableURL = worker
        task.arguments = ["--month", String(format: "%04d-%02d", year, month), "--spreadsheet-id", spreadsheetID, "--config-dir", configDirectory.path]
        task.standardOutput = output
        task.standardError = FileHandle.nullDevice
        task.currentDirectoryURL = configDirectory
        // Python uses the user's system browser for the OAuth consent flow.
        running = true; stage = "authentication"; message = "Connecting to Google…"; progress = nil; completedAt = nil
        process = task
        do { try task.run() } catch {
            running = false; stage = "error"; message = "Could not start the sync worker. Rebuild or reinstall the app."; process = nil; return
        }
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            var buffer = Data()
            var terminal: SyncEvent?
            while true {
                let chunk = output.fileHandleForReading.availableData
                if chunk.isEmpty { break }
                buffer.append(chunk)
                while let newline = buffer.firstIndex(of: 10) {
                    let line = Data(buffer[..<newline])
                    buffer.removeSubrange(...newline)
                    guard let event = try? JSONDecoder().decode(SyncEvent.self, from: line) else { continue }
                    if ["complete", "empty", "error"].contains(event.stage) { terminal = event }
                    else { DispatchQueue.main.async { self?.receive(event) } }
                }
            }
            task.waitUntilExit()
            let result = terminal
            DispatchQueue.main.async {
                guard let self else { return }
                self.running = false; self.process = nil; self.progress = nil
                if task.terminationStatus == 0, let result, ["complete", "empty"].contains(result.stage) {
                    self.receive(result)
                    self.completedAt = Date()
                } else {
                    self.stage = "error"
                    self.message = result?.stage == "error" ? result!.message : "Sync interrupted. The sheet may be partially updated. Retry the full month."
                }
            }
        }
    }

    private func receive(_ event: SyncEvent) {
        stage = event.stage; message = event.message
        if let total = event.total, total > 0, let processed = event.processed {
            progress = Double(processed) / Double(total)
        } else { progress = nil }
    }

    func stopForQuit() {
        process?.terminate()
    }

    func openSheet() {
        guard validSheet, let url = URL(string: "https://docs.google.com/spreadsheets/d/\(spreadsheetID)/edit") else { return }
        NSWorkspace.shared.open(url)
    }
}

struct ContentView: View {
    @ObservedObject var model: SyncModel
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        VStack(spacing: 22) {
            VStack(spacing: 10) {
                Image(systemName: "arrow.triangle.2.circlepath")
                    .font(.system(size: 26, weight: .medium)).foregroundStyle(Color.accentColor)
                    .frame(width: 58, height: 58).background(Color.accentColor.opacity(0.09), in: RoundedRectangle(cornerRadius: 16))
                Text("Choose a month to fully sync.").font(.system(size: 23, weight: .semibold))
                Text("Refresh all SC and DBS transactions for this month in Google Sheets. Your category overrides and Include/Exclude choices are preserved.")
                    .font(.system(size: 12)).foregroundStyle(.secondary).multilineTextAlignment(.center).lineSpacing(3).frame(maxWidth: 410)
            }
            HStack(spacing: 12) {
                Picker("Month", selection: $model.month) {
                    ForEach(1...12, id: \.self) { Text(Calendar.current.monthSymbols[$0 - 1]).tag($0) }
                }.frame(width: 230)
                Picker("Year", selection: $model.year) {
                    ForEach(2000...max(2100, model.year), id: \.self) { Text(String($0)).tag($0) }
                }.frame(width: 140)
            }.disabled(model.running)
            Button(action: model.sync) {
                Text(model.configured ? "Sync \(model.monthTitle)" : "Set up Google connection")
                    .frame(minWidth: 240).padding(.vertical, 5)
            }.buttonStyle(.borderedProminent).controlSize(.large).keyboardShortcut(.return, modifiers: [.command]).disabled(model.running)
                .help("Sync the selected month (⌘Return)")
            VStack(spacing: 8) {
                if model.running {
                    if let progress = model.progress { ProgressView(value: progress).frame(width: 260) }
                    else { ProgressView().controlSize(.small) }
                }
                HStack(alignment: .top, spacing: 6) {
                    if model.stage == "complete" { Image(systemName: "checkmark.circle.fill").foregroundStyle(.green) }
                    if model.stage == "error" { Image(systemName: "exclamationmark.circle.fill").foregroundStyle(.orange) }
                    Text(model.message).foregroundStyle(model.stage == "error" ? .primary : .secondary)
                        .multilineTextAlignment(.center).textSelection(.enabled)
                }.font(.system(size: 12))
                if let completedAt = model.completedAt {
                    Text("Completed at \(completedAt.formatted(date: .omitted, time: .shortened))")
                        .font(.system(size: 11)).foregroundStyle(.tertiary)
                }
            }.frame(minHeight: 55).frame(maxWidth: 420)
            HStack {
                Button { model.showSettings = true } label: { Label("Settings", systemImage: "gearshape") }
                    .buttonStyle(.plain).disabled(model.running).help("Google connection and destination")
                Spacer()
                Button(action: model.openSheet) { Label("Open Google Sheet", systemImage: "arrow.up.right.square") }
                    .buttonStyle(.plain).disabled(!model.validSheet || model.running)
            }.font(.system(size: 12)).foregroundStyle(.secondary)
        }.padding(30).frame(minWidth: 500, idealWidth: 560, minHeight: 440)
            .background(Color(nsColor: .windowBackgroundColor))
            .animation(reduceMotion ? nil : .easeInOut(duration: 0.18), value: model.stage)
            .sheet(isPresented: $model.showSettings) { SettingsView(model: model) }
    }
}

struct SettingsView: View {
    @ObservedObject var model: SyncModel
    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text("Google connection").font(.title2.bold())
            Text("Import Desktop OAuth credentials with Gmail and Google Sheets APIs enabled. Google will open in your browser when you sync.")
                .font(.callout).foregroundStyle(.secondary)
            HStack {
                Label(model.configured ? "Credentials imported" : "Credentials needed", systemImage: model.configured ? "checkmark.circle" : "key")
                Spacer()
                Button("Import credentials…", action: model.importCredentials)
            }
            VStack(alignment: .leading, spacing: 6) {
                Text("Destination spreadsheet ID").font(.callout.weight(.medium))
                TextField("Spreadsheet ID", text: $model.spreadsheetID).textFieldStyle(.roundedBorder)
                Text("The value between /d/ and /edit in your Google Sheets URL.").font(.caption).foregroundStyle(.secondary)
            }
            if let error = model.settingsError { Text(error).font(.callout).foregroundStyle(.red) }
            HStack {
                Spacer()
                Button("Done", action: model.saveSettings).keyboardShortcut(.defaultAction)
            }
        }.padding(24).frame(width: 470)
    }
}

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    weak var model: SyncModel?

    func applicationDidFinishLaunching(_ notification: Notification) {
        // A directly compiled SwiftUI app can start without a regular Dock presence.
        NSApplication.shared.setActivationPolicy(.regular)
        if let iconURL = Bundle.main.url(forResource: "SCAlerts", withExtension: "icns"),
           let icon = NSImage(contentsOf: iconURL) {
            NSApplication.shared.applicationIconImage = icon
        }
        NSApplication.shared.activate(ignoringOtherApps: true)
    }

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        guard let model, model.running else { return .terminateNow }
        let alert = NSAlert()
        alert.messageText = "A sync is still running"
        alert.informativeText = "Quitting will stop the sync. If writing has started, the sheet may be partially updated. You can refresh the month again next time."
        alert.addButton(withTitle: "Keep Syncing")
        alert.addButton(withTitle: "Quit")
        guard alert.runModal() == .alertSecondButtonReturn else { return .terminateCancel }
        model.stopForQuit()
        return .terminateNow
    }
}

@main
struct SCAlertsApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var delegate
    @StateObject private var model = SyncModel()
    var body: some Scene {
        Window("SC Alerts", id: "main") {
            ContentView(model: model).onAppear { delegate.model = model }
        }
            .defaultSize(width: 560, height: 470)
            .windowResizability(.contentMinSize)
            .commands {
                CommandGroup(replacing: .appSettings) {
                    Button("Settings…") { model.showSettings = true }.keyboardShortcut(",").disabled(model.running)
                }
            }
    }
}
