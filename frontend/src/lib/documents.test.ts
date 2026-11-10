import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { uploadDocument } from "./documents";
import { refreshSession } from "./api";
import { exampleDocument } from "../test/document-fixtures";

vi.mock("./api", async (original) => ({
  ...(await original<typeof import("./api")>()),
  refreshSession: vi.fn(),
}));

class FakeXHR {
  static instances: FakeXHR[] = [];
  static respond: (xhr: FakeXHR) => void;
  status = 202;
  responseText = JSON.stringify(exampleDocument);
  withCredentials = false;
  timeout = 0;
  headers = new Map<string, string>();
  body?: FormData;
  upload: {
    onprogress?: (event: {
      lengthComputable: boolean;
      loaded: number;
      total: number;
    }) => void;
  } = {};
  onload = () => {};
  onerror = () => {};
  onabort = () => {};
  ontimeout = () => {};
  constructor() {
    FakeXHR.instances.push(this);
  }
  open = vi.fn();
  setRequestHeader(name: string, value: string) {
    this.headers.set(name, value);
  }
  send(body: FormData) {
    this.body = body;
    queueMicrotask(() => FakeXHR.respond(this));
  }
  abort() {
    this.onabort();
  }
}

beforeEach(() => {
  FakeXHR.instances = [];
  FakeXHR.respond = (xhr) => {
    xhr.upload.onprogress?.({ lengthComputable: true, loaded: 5, total: 10 });
    xhr.onload();
  };
  vi.mocked(refreshSession).mockReset().mockResolvedValue(undefined);
  vi.stubGlobal("XMLHttpRequest", FakeXHR);
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockImplementation(async () => Response.json({ csrf_token: "signed" })),
  );
});
afterEach(() => vi.unstubAllGlobals());

it("uses multipart browser boundaries, CSRF and progress without exposing tokens", async () => {
  const progress = vi.fn();
  expect(
    await uploadDocument(
      "org",
      new File(["text"], "notes.txt"),
      progress,
      new AbortController().signal,
    ),
  ).toEqual(exampleDocument);
  const xhr = FakeXHR.instances[0];
  expect(xhr.withCredentials).toBe(true);
  expect(xhr.headers.get("X-CSRF-Token")).toBe("signed");
  expect(xhr.headers.has("Content-Type")).toBe(false);
  expect(xhr.body?.get("file")).toBeInstanceOf(File);
  expect(progress).toHaveBeenCalledWith(50);
});

it("renews an expired session once before retrying a rejected upload", async () => {
  FakeXHR.respond = (xhr) => {
    if (FakeXHR.instances.length === 1) {
      xhr.status = 401;
      xhr.responseText = JSON.stringify({ detail: "Expired" });
    }
    xhr.onload();
  };
  await uploadDocument(
    "org",
    new File(["text"], "notes.txt"),
    vi.fn(),
    new AbortController().signal,
  );
  expect(refreshSession).toHaveBeenCalledTimes(2);
  expect(FakeXHR.instances).toHaveLength(2);
});

it("aborts an in-flight transfer without retrying", async () => {
  FakeXHR.respond = () => {};
  const controller = new AbortController();
  const promise = uploadDocument(
    "org",
    new File(["text"], "notes.txt"),
    vi.fn(),
    controller.signal,
  );
  const rejected = expect(promise).rejects.toMatchObject({
    name: "AbortError",
  });
  await vi.waitFor(() => expect(FakeXHR.instances).toHaveLength(1));
  controller.abort();
  await rejected;
  expect(FakeXHR.instances).toHaveLength(1);
});
