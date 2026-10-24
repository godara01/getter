"use client";

import { ClerkProvider, SignInButton, UserButton, useAuth } from "@clerk/clerk-react";
import { useEffect, useState } from "react";

import { setTokenGetter } from "@/lib/api";

function TokenBridge({ children }: { children: React.ReactNode }) {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  const [ready, setReady] = useState(false);
  useEffect(() => {
    setTokenGetter(getToken);
    setReady(true);
    return () => setTokenGetter(null);
  }, [getToken]);
  if (!isLoaded || !ready) return <p>Loading sign-in…</p>;
  return (
    <>
      <div className="px-4 py-2">
        {isSignedIn ? <UserButton /> : <SignInButton mode="modal" />}
      </div>
      {children}
    </>
  );
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const key = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;
  if (!key) return children;
  return (
    <ClerkProvider publishableKey={key}>
      <TokenBridge>{children}</TokenBridge>
    </ClerkProvider>
  );
}
