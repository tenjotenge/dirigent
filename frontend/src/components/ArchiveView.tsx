import { useEffect, useState } from "react";
import { exportEncryptedArchive, fetchArchiveSummaries, importEncryptedArchive, type ArchiveSummary } from "../api/client";

interface ArchiveViewProps {
  onBack: () => void;
  onOpen: (id: string) => Promise<void>;
}

export function ArchiveView({ onBack, onOpen }: ArchiveViewProps) {
  const [items, setItems] = useState<ArchiveSummary[]>([]);
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [exportPassphrase, setExportPassphrase] = useState("");
  const [confirmPassphrase, setConfirmPassphrase] = useState("");
  const [importPassphrase, setImportPassphrase] = useState("");

  useEffect(() => {
    let cancelled = false;
    const timer = window.setTimeout(() => {
      fetchArchiveSummaries(search, offset)
        .then((results) => { if (!cancelled) setItems(results); })
        .catch((error) => { if (!cancelled) setMessage(String(error)); });
    }, 200);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [search, offset]);

  const exportAll = async () => {
    if (exportPassphrase.length < 12 || exportPassphrase !== confirmPassphrase) {
      setMessage("Use a passphrase of at least 12 characters and confirm it exactly.");
      return;
    }
    setBusy(true);
    try {
      await exportEncryptedArchive(exportPassphrase);
      setExportPassphrase("");
      setConfirmPassphrase("");
      setMessage("Encrypted archive exported. Keep the passphrase safe; it cannot be recovered.");
    } catch (error) {
      setMessage(String(error));
    } finally {
      setBusy(false);
    }
  };

  const importFile = async (file: File | undefined) => {
    if (!file) return;
    if (!importPassphrase) {
      setMessage("Enter the archive passphrase before selecting a file.");
      return;
    }
    setBusy(true);
    try {
      const result = await importEncryptedArchive(file, importPassphrase);
      setImportPassphrase("");
      setMessage(`Imported ${result.conversations} conversations, ${result.messages} messages, and ${result.runs} runs. Existing IDs were skipped.`);
      setItems(await fetchArchiveSummaries(search, offset));
    } catch (error) {
      setMessage(String(error));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="settings-view">
      <header className="settings-header">
        <button className="btn-ghost" onClick={onBack} type="button">← Back</button>
        <h2>Conversation archive</h2>
      </header>
      <div className="settings-body">
        <section className="settings-section">
          <p className="settings-hint">Search saved conversations, resume one, or consolidate encrypted archives from other Dirigent installations. Exports use Parquet inside a passphrase-protected Dirigent file; the passphrase is not stored and cannot be recovered.</p>
          <input className="settings-input" aria-label="Search conversations" placeholder="Search conversations" value={search} onChange={(event) => { setSearch(event.target.value); setOffset(0); }} />
          <h3>Export all conversations</h3>
          <input className="settings-input" aria-label="Export passphrase" type="password" autoComplete="new-password" placeholder="Passphrase (at least 12 characters)" value={exportPassphrase} onChange={(event) => setExportPassphrase(event.target.value)} />
          <input className="settings-input" aria-label="Confirm export passphrase" type="password" autoComplete="new-password" placeholder="Confirm passphrase" value={confirmPassphrase} onChange={(event) => setConfirmPassphrase(event.target.value)} />
          <div className="settings-actions">
            <button className="btn-secondary" onClick={exportAll} disabled={busy} type="button">Export encrypted Parquet</button>
          </div>
          <h3>Import an encrypted archive</h3>
          <input className="settings-input" aria-label="Import passphrase" type="password" autoComplete="off" placeholder="Archive passphrase" value={importPassphrase} onChange={(event) => setImportPassphrase(event.target.value)} />
          <div className="settings-actions">
            <label className="btn-secondary">
              Import encrypted archive
              <input type="file" accept=".dpa,application/octet-stream" hidden disabled={busy} onChange={(event) => { void importFile(event.target.files?.[0]); event.target.value = ""; }} />
            </label>
          </div>
          {message && <p className="settings-result">{message}</p>}
        </section>
        <section className="settings-section">
          <h3>Saved conversations</h3>
          {items.length === 0 && <p className="settings-hint">No conversations found.</p>}
          {items.map((item) => (
            <div className="confirm-detail" key={item.id}>
              <div className="confirm-value">
                <strong>{item.title}</strong>
                <p className="settings-hint">{new Date(item.updated_at).toLocaleString()} · {item.run_count} run{item.run_count === 1 ? "" : "s"} · {item.last_provider || "unknown provider"} · {item.last_model || "unknown model"} · effort: {item.last_effort || "unknown"}</p>
                <div className="settings-actions">
                  <button className="btn-secondary" type="button" onClick={() => void onOpen(item.id).catch((error) => setMessage(String(error)))}>Open</button>
                </div>
              </div>
            </div>
          ))}
          <div className="settings-actions">
            <button className="btn-secondary" type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 50))}>Previous</button>
            <button className="btn-secondary" type="button" disabled={items.length < 50} onClick={() => setOffset(offset + 50)}>Next</button>
          </div>
        </section>
      </div>
    </div>
  );
}
