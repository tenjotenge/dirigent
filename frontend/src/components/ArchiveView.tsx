import { useEffect, useState } from "react";
import { downloadArchive, fetchArchiveSummaries, importArchive, type ArchiveSummary } from "../api/client";

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
    setBusy(true);
    try {
      await downloadArchive("/archive/export.json", "dirigent-archive.json");
      setMessage("Archive exported. Store this file securely; it contains full conversation text.");
    } catch (error) {
      setMessage(String(error));
    } finally {
      setBusy(false);
    }
  };

  const importFile = async (file: File | undefined) => {
    if (!file) return;
    setBusy(true);
    try {
      const result = await importArchive(JSON.parse(await file.text()));
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
          <p className="settings-hint">Search saved conversations, resume one, or consolidate archives from other Dirigent installations.</p>
          <input className="settings-input" aria-label="Search conversations" placeholder="Search conversations" value={search} onChange={(event) => { setSearch(event.target.value); setOffset(0); }} />
          <div className="settings-actions">
            <button className="btn-secondary" onClick={exportAll} disabled={busy} type="button">Export all as JSON</button>
            <label className="btn-secondary">
              Import JSON
              <input type="file" accept="application/json,.json" hidden disabled={busy} onChange={(event) => { void importFile(event.target.files?.[0]); event.target.value = ""; }} />
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
                  <button className="btn-secondary" type="button" onClick={() => void downloadArchive(`/archive/conversations/${encodeURIComponent(item.id)}/export.md`, `dirigent-${item.id}.md`).catch((error) => setMessage(String(error)))}>Export Markdown</button>
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
