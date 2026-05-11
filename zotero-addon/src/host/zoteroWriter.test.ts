import { describe, expect, it } from "vitest";

import type { NormalizedPaper } from "../shared/contracts";
import type { ZoteroGlobal } from "./zoteroTypes";
import { nativeWrite } from "./zoteroWriter";

// Minimal paper factory used across test cases.
function makePaper(overrides?: Partial<NormalizedPaper>): NormalizedPaper {
  return {
    abstract: null,
    arxiv_id: null,
    authors: ["Author One"],
    citation_count: 0,
    doi: null,
    index: 1,
    influential_citation_count: 0,
    open_access: false,
    pdf_url: null,
    score: 1,
    semantic_score: 1,
    source: "test",
    summary: null,
    explanation: null,
    title: "Test Paper",
    url: null,
    year: 2024,
    ...overrides,
  };
}

// Incrementing key counter to prevent cross-test collisions.
let keyCounter = 0;
function nextKey(): string {
  keyCounter += 1;
  return `item${String(keyCounter)}`;
}

// Minimal ZoteroGlobal mock with configurable behaviours.
interface MockZoteroOptions {
  /** Whether Attachments.importFromURL resolves to a truthy value (success). */
  attachSuccess?: boolean;
}

function createMockZotero(options: MockZoteroOptions = {}): ZoteroGlobal {
  const { attachSuccess = true } = options;
  const storedItems: Array<{
    id: number;
    key: string;
    getField: (f: string) => string;
    setField: () => void;
    addToCollection: () => void;
    save: () => Promise<void>;
    libraryID: number;
  }> = [];

  return {
    ItemPaneManager: { registerSection: () => "s", unregisterSection: () => undefined },
    PreferencePanes: { register: () => undefined },
    Prefs: { get: () => undefined, set: () => undefined },
    Collections: {
      getByLibrary: () => [],
      getByParent: () => [],
      add: () =>
        Promise.resolve({ id: 1, key: "col1", name: "Inbox", parentKey: false, libraryID: 1 }),
      get: () => false,
      getAsync: () => Promise.resolve(false),
    },
    Items: {
      getAll: () => storedItems as ReturnType<ZoteroGlobal["Items"]["getAll"]>,
      getAsync: () => Promise.resolve(false),
      get: () => false,
      add: (_fields: unknown, _libraryID: number) => {
        const key = nextKey();
        const item = {
          id: keyCounter,
          key,
          libraryID: 1,
          getField: (f: string) => {
            if (f === "DOI") return (_fields as { DOI?: string }).DOI ?? "";
            if (f === "title") return (_fields as { title?: string }).title ?? "";
            if (f === "firstCreator") return "Author One";
            return "";
          },
          setField: () => undefined,
          addToCollection: () => undefined,
          save: () => Promise.resolve(),
        };
        storedItems.push(item);
        return Promise.resolve(item);
      },
    },
    Attachments: {
      importFromURL: () => Promise.resolve(attachSuccess ? { id: 99 } : false),
    },
    Libraries: {
      getUserLibrary: () => ({ libraryID: 1, name: "My Library", editable: true }),
    },
    debug: () => undefined,
    getMainWindows: () => [],
    logError: () => undefined,
  } as unknown as ZoteroGlobal;
}

describe("nativeWrite — PDF status tracking", () => {
  it("sets pdfStatus=null for all outcomes when enablePdfImport=false", async () => {
    const paper = makePaper({ pdf_url: "https://example.com/paper.pdf" });
    const result = await nativeWrite([paper], "Inbox", false, createMockZotero());

    expect(result.pdfAttached).toBe(0);
    expect(result.pdfFailed).toBe(0);
    expect(result.outcomes[0]?.pdfStatus).toBeNull();
  });

  it("sets pdfStatus='attached' when pdf_url is present and attach succeeds", async () => {
    const paper = makePaper({ pdf_url: "https://example.com/paper.pdf" });
    const result = await nativeWrite([paper], "Inbox", true, createMockZotero({ attachSuccess: true }));

    expect(result.pdfAttached).toBe(1);
    expect(result.pdfFailed).toBe(0);
    expect(result.outcomes[0]?.pdfStatus).toBe("attached");
    expect(result.outcomes[0]?.status).toBe("created");
  });

  it("sets pdfStatus='failed' when pdf_url is present but attach fails", async () => {
    const paper = makePaper({ pdf_url: "https://example.com/paper.pdf" });
    const result = await nativeWrite([paper], "Inbox", true, createMockZotero({ attachSuccess: false }));

    expect(result.pdfAttached).toBe(0);
    expect(result.pdfFailed).toBe(1);
    expect(result.outcomes[0]?.pdfStatus).toBe("failed");
  });

  it("sets pdfStatus='skipped' when the paper has no pdf_url", async () => {
    const paper = makePaper({ pdf_url: null });
    const result = await nativeWrite([paper], "Inbox", true, createMockZotero());

    expect(result.pdfAttached).toBe(0);
    expect(result.pdfFailed).toBe(0);
    expect(result.outcomes[0]?.pdfStatus).toBe("skipped");
    expect(result.outcomes[0]?.status).toBe("created");
  });

  it("sets pdfStatus=null for unchanged (duplicate) items regardless of pdf_url", async () => {
    // Use a DOI-based paper and pre-populate the library via a first write.
    const paper = makePaper({ doi: "10.1000/test.dup", pdf_url: "https://example.com/p.pdf" });
    const zotero = createMockZotero();

    // First write creates the item.
    await nativeWrite([paper], "Inbox", false, zotero);

    // Second write should detect duplicate via DOI and set pdfStatus=null.
    const result = await nativeWrite([paper], "Inbox", true, zotero);
    expect(result.unchanged).toBe(1);
    expect(result.created).toBe(0);
    expect(result.outcomes[0]?.status).toBe("unchanged");
    expect(result.outcomes[0]?.pdfStatus).toBeNull();
  });

  it("reports mixed pdfAttached and pdfFailed across multiple papers", async () => {
    const withPdf = makePaper({ title: "Paper With PDF", pdf_url: "https://example.com/a.pdf" });
    const noPdf = makePaper({ title: "Paper Without PDF", pdf_url: null });
    const result = await nativeWrite(
      [withPdf, noPdf],
      "Inbox",
      true,
      createMockZotero({ attachSuccess: true }),
    );

    expect(result.created).toBe(2);
    expect(result.pdfAttached).toBe(1);
    expect(result.pdfFailed).toBe(0);
    const withPdfOutcome = result.outcomes.find((o) => o.paper.title === "Paper With PDF");
    const noPdfOutcome = result.outcomes.find((o) => o.paper.title === "Paper Without PDF");
    expect(withPdfOutcome?.pdfStatus).toBe("attached");
    expect(noPdfOutcome?.pdfStatus).toBe("skipped");
  });
});
