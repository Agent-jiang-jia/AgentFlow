export interface CsvPreview {
  rows: string[][];
  truncated: boolean;
}

export function parseCsvPreview(content: string, maxRows = 500): CsvPreview {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let quoted = false;

  const pushRow = () => {
    row.push(field);
    rows.push(row);
    row = [];
    field = "";
  };

  for (let index = 0; index < content.length; index += 1) {
    const character = content[index];
    if (quoted) {
      if (character === '"' && content[index + 1] === '"') {
        field += '"';
        index += 1;
      } else if (character === '"') {
        quoted = false;
      } else {
        field += character;
      }
    } else if (character === '"' && field.length === 0) {
      quoted = true;
    } else if (character === ",") {
      row.push(field);
      field = "";
    } else if (character === "\n") {
      pushRow();
      if (rows.length > maxRows) {
        return { rows: rows.slice(0, maxRows), truncated: true };
      }
    } else if (character !== "\r") {
      field += character;
    }
  }
  if (field.length > 0 || row.length > 0) {
    pushRow();
  }
  return { rows: rows.slice(0, maxRows), truncated: rows.length > maxRows };
}
