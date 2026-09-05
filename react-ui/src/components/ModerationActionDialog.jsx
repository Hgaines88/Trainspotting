import { useEffect, useRef, useState } from "react";

const ACTION_COPY = {
  approve: {
    title: "Approve proposal",
    description: "Approve and promote this proposal into the public archive?",
    confirmLabel: "Approve and publish",
  },
  request_changes: {
    title: "Request changes",
    description: "Explain what the contributor must change before this proposal can be reviewed again.",
    confirmLabel: "Send change request",
    notesLabel: "Required changes",
  },
  reject: {
    title: "Reject proposal",
    description: "Explain why this proposal should not be added to the archive.",
    confirmLabel: "Reject proposal",
    notesLabel: "Rejection reason",
    danger: true,
  },
  rollback: {
    title: "Roll back approval",
    description: "Restore the pre-approval archive state? This destructive action is recorded in the audit history.",
    confirmLabel: "Restore previous state",
    notesLabel: "Rollback reason",
    danger: true,
  },
};

export default function ModerationActionDialog({ action, busy, onCancel, onConfirm }) {
  const dialogRef = useRef(null);
  const notesRef = useRef(null);
  const [notes, setNotes] = useState("");
  const copy = action ? ACTION_COPY[action] : null;

  useEffect(() => {
    const dialog = dialogRef.current;
    if (action && !dialog.open) {
      setNotes("");
      dialog.showModal();
      requestAnimationFrame(() => (copy.notesLabel ? notesRef.current : dialog.querySelector("button[type='submit']"))?.focus());
    } else if (!action && dialog.open) dialog.close();
  }, [action, copy?.notesLabel]);

  function submit(event) {
    event.preventDefault();
    const normalizedNotes = notes.trim();
    if (copy.notesLabel && !normalizedNotes) {
      notesRef.current?.focus();
      return;
    }
    onConfirm(normalizedNotes || null);
  }

  return <dialog
    aria-describedby="moderation-action-description"
    aria-labelledby="moderation-action-title"
    className="moderation-dialog"
    onCancel={(event) => { event.preventDefault(); if (!busy) onCancel(); }}
    ref={dialogRef}
  >
    {copy && <form method="dialog" onSubmit={submit}>
      <p className="eyebrow">Review decision</p>
      <h2 id="moderation-action-title">{copy.title}</h2>
      <p id="moderation-action-description">{copy.description}</p>
      {copy.notesLabel && <label>{copy.notesLabel}
        <textarea ref={notesRef} required rows="5" value={notes} onChange={(event) => setNotes(event.target.value)} />
      </label>}
      <div className="actions">
        <button type="button" className="secondary" disabled={busy} onClick={onCancel}>Cancel</button>
        <button type="submit" className={copy.danger ? "danger" : ""} disabled={busy}>{busy ? "Working…" : copy.confirmLabel}</button>
      </div>
    </form>}
  </dialog>;
}
