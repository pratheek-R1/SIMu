"use client";

import { useEffect, useState } from "react";
import { useStore } from "@/lib/store";

export default function Toasts() {
  const { toasts } = useStore();
  return (
    <div className="toastwrap">
      {toasts.map((t) => (
        <Toast key={t.id} title={t.title} message={t.message} />
      ))}
    </div>
  );
}

function Toast({ title, message }: { title: string; message: string }) {
  const [show, setShow] = useState(false);
  useEffect(() => {
    const id = setTimeout(() => setShow(true), 10);
    return () => clearTimeout(id);
  }, []);
  return (
    <div className={`toast${show ? " show" : ""}`} role="status">
      <div className="tt">{title}</div>
      <div className="tm">{message}</div>
    </div>
  );
}
