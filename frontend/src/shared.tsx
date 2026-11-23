import { createContext, useContext, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { CircleAlert, Inbox, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { request } from "./api";
import { display, label } from "./domain";

export function useResource<T>(path: string | null, revision = 0) {
  const [result, setResult] = useState<{ path: string; data: T }>();
  const [error, setError] = useState<{ path: string; message: string }>();
  useEffect(() => {
    if (!path) return;
    const controller = new AbortController();
    request<T>(path, "GET", undefined, controller.signal).then(data => {
      if (controller.signal.aborted) return;
      setResult({ path, data });
      setError(undefined);
    }).catch((reason: Error) => {
      if (!controller.signal.aborted) setError({ path, message: reason.message });
    });
    return () => controller.abort();
  }, [path, revision]);
  return { data: result && result.path === path ? result.data : undefined, error: error && error.path === path ? error.message : undefined };
}

export type Mutate = <T>(path: string, method?: string, body?: unknown, message?: string) => Promise<T | undefined>;
export type PageProps = { state: import("./api").State; mutate: Mutate; revision: number; busy: boolean };

export function Heading({ title, description, children }: { title: string; description: string; children?: ReactNode }) {
  return <header className="page-heading"><div><h1 className="page-title">{title}</h1><p className="page-subtitle">{description}</p></div>{children && <div className="page-actions">{children}</div>}</header>;
}

export function Panel({ title, caption, children }: { title: string; caption?: string; children: ReactNode }) {
  return <Card className="workspace-panel">{title && <CardHeader><h2>{title}</h2>{caption && <p>{caption}</p>}</CardHeader>}<CardContent>{children}</CardContent></Card>;
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty"><Inbox size={21}/><p>{children}</p></div>;
}

export function ErrorNotice({ message }: { message?: string }) {
  return message && <div role="alert" className="alert"><CircleAlert size={16}/><span>{message}</span></div>;
}

export function Loading() {
  return <div className="loading-grid" role="status" aria-label="Loading">{Array.from({length: 6}, (_, index) => <div key={index} className="skeleton"/>)}</div>;
}

export function Status({ value, tone }: { value?: string; tone?: "good" | "warn" | "bad" }) {
  return <Badge variant="outline" className={"state-badge " + (tone ?? "")}>{label(value)}</Badge>;
}

export function Details({ values }: { values: Record<string, unknown> }) {
  return <dl className="details">{Object.entries(values).map(([name, value]) =>
    <div key={name}><dt>{label(name)}</dt><dd>{display(value)}</dd></div>
  )}</dl>;
}

export const Feedback = createContext({error: "", success: ""});

export function Modal({ title, close, drawer, children }: { title: string; close: () => void; drawer?: boolean; children: ReactNode }) {
  const feedback = useContext(Feedback);
  const dialog = useRef<HTMLDialogElement>(null);
  const closeRef = useRef(close);
  useEffect(() => { closeRef.current = close; }, [close]);
  useEffect(() => {
    const element = dialog.current;
    const previous = document.activeElement;
    element?.showModal();
    return () => {
      element?.close();
      if (previous instanceof HTMLElement) previous.focus();
    };
  }, []);
  return <dialog ref={dialog} className={drawer ? "workspace-drawer" : "workspace-dialog"} aria-label={title}
    onCancel={event => { event.preventDefault(); closeRef.current(); }} onClick={event => {
      if (event.target === event.currentTarget) {
        const bounds = event.currentTarget.getBoundingClientRect();
        if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) closeRef.current();
      }
    }}>
    <header className="drawer-head"><h2>{title}</h2><Button type="button" variant="ghost" size="icon" onClick={close} aria-label="Close"><X size={19}/></Button></header>
    <div className="drawer-body"><ErrorNotice message={feedback.error}/>{feedback.success && <p className="inline-success" role="status">{feedback.success}</p>}{children}</div>
  </dialog>;
}
