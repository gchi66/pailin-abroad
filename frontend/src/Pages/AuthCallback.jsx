import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { API_BASE_URL } from "../config/api";
import supabaseClient from "../supabaseClient";

const getCallbackParams = () => {
  const query = new URLSearchParams(window.location.search);
  const hash = new URLSearchParams(window.location.hash.replace(/^#/, ""));

  return {
    code: query.get("code"),
    error: query.get("error") || hash.get("error"),
    errorDescription:
      query.get("error_description") ||
      hash.get("error_description") ||
      query.get("error_code") ||
      hash.get("error_code"),
    accessToken: hash.get("access_token"),
    refreshToken: hash.get("refresh_token"),
  };
};

const AuthCallback = () => {
  const navigate = useNavigate();
  const [error, setError] = useState("");

  useEffect(() => {
    let isMounted = true;

    const finishAuthentication = async () => {
      try {
        const callback = getCallbackParams();

        if (callback.error || callback.errorDescription) {
          throw new Error(
            callback.errorDescription ||
              callback.error ||
              "This authentication link is invalid or has expired."
          );
        }

        // Supabase initializes the client by consuming callback parameters when
        // possible. Check that result first so a PKCE code is not exchanged
        // twice by the client initialization and this page.
        const { data: initializedData, error: initializedSessionError } =
          await supabaseClient.auth.getSession();
        if (initializedSessionError) throw initializedSessionError;

        let session = initializedData.session;

        if (!session && callback.code) {
          const { data, error: exchangeError } =
            await supabaseClient.auth.exchangeCodeForSession(callback.code);
          if (exchangeError) throw exchangeError;
          session = data.session;
        } else if (
          !session &&
          callback.accessToken &&
          callback.refreshToken
        ) {
          const { data, error: sessionError } =
            await supabaseClient.auth.setSession({
              access_token: callback.accessToken,
              refresh_token: callback.refreshToken,
          });
          if (sessionError) throw sessionError;
          session = data.session;
        }

        if (!session?.access_token) {
          throw new Error(
            "We couldn't complete authentication. The link may have expired or already been used."
          );
        }

        const syncResponse = await fetch(`${API_BASE_URL}/api/confirm-email`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${session.access_token}`,
            "Content-Type": "application/json",
          },
        });
        const syncData = await syncResponse.json().catch(() => ({}));

        if (!syncResponse.ok) {
          throw new Error(
            syncData.error || "We couldn't finish setting up your account."
          );
        }

        const { data: profile, error: profileError } = await supabaseClient
          .from("users")
          .select("onboarding_completed")
          .eq("id", session.user.id)
          .single();

        if (profileError) throw profileError;

        if (isMounted) {
          navigate(profile?.onboarding_completed ? "/pathway" : "/onboarding", {
            replace: true,
          });
        }
      } catch (callbackError) {
        console.error("Authentication callback failed:", callbackError);
        if (isMounted) {
          setError(
            callbackError.message ||
              "We couldn't complete authentication. Please request a new link."
          );
        }
      }
    };

    finishAuthentication();

    return () => {
      isMounted = false;
    };
  }, [navigate]);

  return (
    <main
      style={{
        alignItems: "center",
        display: "flex",
        justifyContent: "center",
        minHeight: "100vh",
        padding: "2rem",
      }}
    >
      <div style={{ maxWidth: "34rem", textAlign: "center" }}>
        <h1>{error ? "Unable to continue" : "Confirming your account…"}</h1>
        {error ? (
          <>
            <p>{error}</p>
            <p>
              Return to the <Link to="/">home page</Link> to request a new link.
            </p>
          </>
        ) : (
          <p>Please wait while we securely finish signing you in.</p>
        )}
      </div>
    </main>
  );
};

export default AuthCallback;
