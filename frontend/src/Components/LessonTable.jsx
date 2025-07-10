import React from "react";
import "../Styles/LessonTable.css"; // Assuming you have a CSS file for styling

export default function LessonTable({ data }) {
  return (
    <div className="lesson-table-wrapper">
      <table>
        <tbody>
          {data.cells.map((row, rIdx) => (
            <tr key={rIdx}>
              {row.map((cell, cIdx) => (
                <td key={cIdx}>
                  {/* split on \n so each line sits on its own row inside the cell */}
                  {cell.split("\n").map((line, i) => (
                    <div key={i}>{line}</div>
                  ))}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
