"use client";
import { useState, useEffect } from "react";

export default function Home() {
  const [status, setStatus] = useState("");

  useEffect(() => {
    fetch("http://localhost:8000/")
      .then(res => res.json())
      .then(data => setStatus(data.message));
  }, []);

  return (
    <main className="flex min-h-screen items-center justify-center">
      <div className="text-center">
        <h1 className="text-4xl font-bold">AI Security Scanner</h1>
        <p className="mt-4 text-gray-600">Backend status: {status}</p>
      </div>
    </main>
  );
}