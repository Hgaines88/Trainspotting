export default function CorrectionField({ label, action, onActionChange, canClear, children }) {
  const actionId = `correction-action-${label.toLocaleLowerCase().replaceAll(/[^a-z0-9]+/g, "-")}`;
  return <fieldset className="correction-field">
    <legend>{label}</legend>
    <label htmlFor={actionId}>Change action for {label}</label>
    <select
      id={actionId}
      value={action}
      onChange={(event) => onActionChange(event.target.value)}
    >
      <option value="unchanged">Keep unchanged</option>
      <option value="replace">Replace value</option>
      {canClear && <option value="clear">Clear field</option>}
    </select>
    {action === "replace" && children}
    {action === "clear" && <small>This field will be cleared if the proposal is approved.</small>}
  </fieldset>;
}
