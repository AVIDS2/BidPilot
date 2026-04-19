import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { App } from "./app";

test("renders DocPilot shell", () => {
  render(<App />);
  expect(screen.getByText("DocPilot Workbench")).toBeInTheDocument();
});
