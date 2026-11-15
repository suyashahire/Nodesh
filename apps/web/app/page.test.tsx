import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import HomePage from "./page";

describe("HomePage", () => {
  it("presents the Nodesh product shell", () => {
    const page = renderToStaticMarkup(<HomePage />);

    expect(page).toContain("Preparing your private workspace");
  });
});
