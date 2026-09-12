interface Props {
  disabled?: boolean;
  onClick: () => void;
}

/** Primary action: triggers idea generation. */
export default function GenerateButton({ disabled, onClick }: Props) {
  return (
    <button id="generate_button" className="generate-button" disabled={disabled} onClick={onClick}>
      Generar
    </button>
  );
}
