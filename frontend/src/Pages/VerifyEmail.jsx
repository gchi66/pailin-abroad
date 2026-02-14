import React, { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../AuthContext";
import supabaseClient from "../supabaseClient";
import { API_BASE_URL } from "../config/api";

const VerifyEmail = () => {
  const navigate = useNavigate();
  const { user } = useAuth();

  useEffect(() => {
    const updateVerificationStatus = async () => {
      if (user && user.email_confirmed_at) {

        try {
          // Call backend to confirm email and create/sync user record
          const resp = await fetch(`${API_BASE_URL}/api/confirm-email`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json'
            },
            body: JSON.stringify({ access_token: user.access_token })
          });

          const data = await resp.json();

          if (resp.ok) {
            navigate('/onboarding');
            return;
          } else {
            console.warn('Backend confirm-email failed, falling back to local DB update:', data);
          }
        } catch (err) {
          console.warn('Error calling backend confirm-email, falling back to local DB update:', err);
        }

        // Fallback: Update is_verified in database directly (resilient backup)
        try {
          const { error } = await supabaseClient
            .from('users')
            .update({ is_verified: true })
            .eq('id', user.id);

          if (error) {
            console.error('Error updating is_verified locally:', error);
          } else {
          }
        } catch (err) {
          console.error('Fallback DB update failed:', err);
        }

        navigate('/onboarding');
      }
    };

    updateVerificationStatus();
  }, [user, navigate]);

  return (
    <div style={{
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      minHeight: '100vh',
      fontFamily: 'Poppins, Anuphan, sans-serif'
    }}>
      <div style={{ textAlign: 'center' }}>
        <h2>Verifying your email...</h2>
        <p>Please wait while we verify your account.</p>
      </div>
    </div>
  );
};

export default VerifyEmail;
