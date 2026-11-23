import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { Heading, Panel, Status } from "./shared";

describe("workspace components", () => {
  it("renders semantic page and panel titles with descriptive content", () => {
    const markup = renderToStaticMarkup(<>
      <Heading title="Job discovery" description="Review saved postings."/>
      <Panel title="Eligibility"><Status value="NEEDS_REVIEW" tone="warn"/></Panel>
    </>);
    expect(markup).toContain('<h1 class="page-title">Job discovery</h1>');
    expect(markup).toContain("<h2>Eligibility</h2>");
    expect(markup).toContain("state-badge warn");
    expect(markup).toContain(">Needs review<");
  });
});
