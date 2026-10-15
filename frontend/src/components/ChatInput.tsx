import { useRef, useEffect, useState } from "react";
import type { PromptAttachment } from "../types";

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  attachments: PromptAttachment[];
  onAttachmentsChange: (attachments: PromptAttachment[]) => void;
  disabled: boolean;
  placeholder?: string;
}

export function ChatInput({
  value,
  onChange,
  onSend,
  attachments,
  onAttachmentsChange,
  disabled,
  placeholder = "Enter instruction… (Enter to send, Shift+Enter for newline)",
}: ChatInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [attachmentError, setAttachmentError] = useState("");

  const addFiles = async (selection: FileList | null) => {
    if (!selection?.length) return;
    try {
      const next = [...attachments];
      for (const file of Array.from(selection)) {
        if (next.length >= 4) throw new Error("Attach at most four text files.");
        if (file.size > 32 * 1024) throw new Error(`${file.name} exceeds 32 KiB.`);
        if (!file.name || file.name.length > 120 || /[\\/\x00-\x1f]/.test(file.name)) throw new Error("Use simple attachment filenames.");
        if (next.some((item) => item.name === file.name)) throw new Error(`${file.name} is already attached.`);
        const content = new TextDecoder("utf-8", { fatal: true }).decode(await file.arrayBuffer());
        if (content.includes("\0")) throw new Error(`${file.name} is not a UTF-8 text file.`);
        next.push({ name: file.name, content });
      }
      const bytes = next.reduce((sum, file) => sum + new TextEncoder().encode(file.content).length, 0);
      if (bytes > 64 * 1024) throw new Error("Attachments exceed 64 KiB combined.");
      onAttachmentsChange(next);
      setAttachmentError("");
    } catch (error) {
      setAttachmentError(error instanceof Error ? error.message : String(error));
    }
  };

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [value]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!disabled && (value.trim() || attachments.length > 0)) {
        onSend();
      }
    }
  };

  return (
    <div className="chat-input-area">
      {attachments.length > 0 && <div className="prompt-attachments">
        {attachments.map((file) => <button key={file.name} type="button" disabled={disabled}
          title={`Remove ${file.name}`} onClick={() => onAttachmentsChange(attachments.filter((item) => item.name !== file.name))}>
          {file.name} ×
        </button>)}
      </div>}
      {attachmentError && <p className="prompt-attachment-error" role="alert">{attachmentError}</p>}
      <textarea
        ref={textareaRef}
        className="chat-textarea"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={disabled}
        rows={3}
      />
      <button className="prompt-attach-button" type="button" disabled={disabled}
        onClick={() => fileInputRef.current?.click()}>
        Attach UTF-8 text (4 files, 64 KiB total)
      </button>
      <input ref={fileInputRef} type="file" multiple accept="text/*,.md,.json,.csv,.py,.ts,.tsx,.js,.jsx,.yaml,.yml,.toml" hidden disabled={disabled}
        onChange={(event) => { void addFiles(event.target.files); event.target.value = ""; }} />
      <button
        className="send-button"
        onClick={onSend}
        disabled={disabled || (!value.trim() && attachments.length === 0)}
      >
        Send
      </button>
    </div>
  );
}
