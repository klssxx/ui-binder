interface Props {
  value: string;
  onChange: (v: string) => void;
}

/** Prompt input for the idea generator. */
export default function IdeaInput({ value, onChange }: Props) {
  return (
    <input
      id="idea_input"
      className="idea-input"
      value={value}
      placeholder="Describe your idea..."
      onChange={(e) => onChange(e.target.value)}
    />
  );
}
