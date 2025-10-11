import React, { useState, useEffect } from "react";
import { useAuth } from "../AuthContext";
import supabaseClient from "../supabaseClient";
import { format } from "date-fns";
import "../Styles/SubscriptionBilling.css";

const SubscriptionBilling = () => {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState({});
  const [error, setError] = useState(null);

  // User profile state
  const [userProfile, setUserProfile] = useState(null);

  // Payment method state
  const [paymentMethod, setPaymentMethod] = useState(null);

  // Invoices state
  const [invoices, setInvoices] = useState([]);

  // Cancellation state
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);

  // Fetch subscription data on mount
  useEffect(() => {
    const fetchSubscriptionData = async () => {
      if (!user) {
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setError(null);

        // Fetch user profile from Supabase
        const { data: profile, error: profileError } = await supabaseClient
          .from("users")
          .select("stripe_subscription_id, subscription_status, current_period_end, is_paid")
          .eq("id", user.id)
          .single();

        if (profileError) throw profileError;
        setUserProfile(profile);

        // Only fetch Stripe data if user has an active subscription
        if (profile?.stripe_subscription_id && profile?.is_paid) {
          // Fetch payment method
          await fetchPaymentMethod();

          // Fetch invoices
          await fetchInvoices();
        }

        setLoading(false);
      } catch (err) {
        console.error("Error fetching subscription data:", err);
        setError("Failed to load subscription information");
        setLoading(false);
      }
    };

    fetchSubscriptionData();
  }, [user]);

  const fetchPaymentMethod = async () => {
    try {
      const { data: { session } } = await supabaseClient.auth.getSession();
      if (!session?.access_token) return;

      const response = await fetch("http://127.0.0.1:5000/api/get-payment-method", {
        method: "GET",
        headers: {
          "Authorization": `Bearer ${session.access_token}`,
          "Content-Type": "application/json"
        }
      });

      if (response.ok) {
        const data = await response.json();
        setPaymentMethod(data.payment_method);
      } else {
        console.error("Failed to fetch payment method");
      }
    } catch (err) {
      console.error("Error fetching payment method:", err);
    }
  };

  const fetchInvoices = async () => {
    try {
      const { data: { session } } = await supabaseClient.auth.getSession();
      if (!session?.access_token) return;

      const response = await fetch("http://127.0.0.1:5000/api/get-invoices", {
        method: "GET",
        headers: {
          "Authorization": `Bearer ${session.access_token}`,
          "Content-Type": "application/json"
        }
      });

      if (response.ok) {
        const data = await response.json();
        setInvoices(data.invoices || []);
      } else {
        console.error("Failed to fetch invoices");
      }
    } catch (err) {
      console.error("Error fetching invoices:", err);
    }
  };

  const handleChangePlan = async () => {
    try {
      setActionLoading({ ...actionLoading, changePlan: true });

      const { data: { session } } = await supabaseClient.auth.getSession();
      if (!session?.access_token) {
        alert("Please log in to manage your subscription");
        return;
      }

      const response = await fetch("http://127.0.0.1:5000/api/create-portal-session", {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${session.access_token}`,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          return_url: `${window.location.origin}/account-settings`
        })
      });

      if (response.ok) {
        const data = await response.json();
        window.location.href = data.url;
      } else {
        const errorData = await response.json();
        alert(`Error: ${errorData.error || "Failed to open billing portal"}`);
      }
    } catch (err) {
      console.error("Error opening portal:", err);
      alert("Something went wrong. Please try again.");
    } finally {
      setActionLoading({ ...actionLoading, changePlan: false });
    }
  };

  const handleEditPayment = async () => {
    // Same as change plan - both go to Stripe portal
    await handleChangePlan();
  };

  const handleDownloadInvoice = async (invoiceId) => {
    try {
      setActionLoading({ ...actionLoading, [`invoice_${invoiceId}`]: true });

      const { data: { session } } = await supabaseClient.auth.getSession();
      if (!session?.access_token) return;

      const response = await fetch(`http://127.0.0.1:5000/api/download-invoice/${invoiceId}`, {
        method: "GET",
        headers: {
          "Authorization": `Bearer ${session.access_token}`
        }
      });

      if (response.ok) {
        const data = await response.json();
        // Open PDF in new tab
        if (data.pdf_url) {
          window.open(data.pdf_url, '_blank');
        }
      } else {
        alert("Failed to download invoice");
      }
    } catch (err) {
      console.error("Error downloading invoice:", err);
      alert("Something went wrong. Please try again.");
    } finally {
      setActionLoading({ ...actionLoading, [`invoice_${invoiceId}`]: false });
    }
  };

  const handleCancelSubscription = async () => {
    if (!showCancelConfirm) {
      setShowCancelConfirm(true);
      return;
    }

    try {
      setActionLoading({ ...actionLoading, cancel: true });

      const { data: { session } } = await supabaseClient.auth.getSession();
      if (!session?.access_token) return;

      const response = await fetch("http://127.0.0.1:5000/api/cancel-subscription", {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${session.access_token}`,
          "Content-Type": "application/json"
        }
      });

      if (response.ok) {
        const data = await response.json();

        // Update local state
        setUserProfile({
          ...userProfile,
          is_paid: false,
          subscription_status: 'canceled'
        });

        setShowCancelConfirm(false);
        alert(data.message || "Your subscription has been cancelled. You'll retain access until the end of your billing period.");
      } else {
        const errorData = await response.json();
        alert(`Error: ${errorData.error || "Failed to cancel subscription"}`);
      }
    } catch (err) {
      console.error("Error cancelling subscription:", err);
      alert("Something went wrong. Please try again.");
    } finally {
      setActionLoading({ ...actionLoading, cancel: false });
    }
  };

  const formatCurrency = (amount) => {
    if (!amount) return "฿0";
    return `฿${(amount / 100).toFixed(0)}`;
  };

  const formatDate = (dateString) => {
    if (!dateString) return "N/A";
    try {
      return format(new Date(dateString), "MMMM dd, yyyy");
    } catch {
      return "N/A";
    }
  };

  if (loading) {
    return (
      <div className="subscription-billing">
        <div className="loading-container">
          <div className="spinner"></div>
          <p>Loading subscription details...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="subscription-billing">
        <div className="error-container">
          <p className="error-message">{error}</p>
          <button className="retry-btn" onClick={() => window.location.reload()}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (!userProfile?.is_paid) {
    return (
      <div className="subscription-billing">
        <div className="no-subscription">
          <h3>No Active Subscription</h3>
          <p>You don't currently have an active subscription.</p>
          <button className="primary-btn" onClick={() => window.location.href = "/membership"}>
            View Plans
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="subscription-billing">
      {/* SUBSCRIPTION SECTION */}
      <section className="billing-section">
        <h3 className="section-title">SUBSCRIPTION</h3>
        <div className="subscription-details">
          <div className="detail-row">
            <span className="detail-label">Current Plan</span>
            <span className="detail-value">Premium Monthly</span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Next Billing Date</span>
            <span className="detail-value">
              {formatDate(userProfile?.current_period_end)}
            </span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Price</span>
            <span className="detail-value">฿400/month</span>
          </div>
          <div className="detail-row">
            <span className="detail-label">Status</span>
            <span className={`status-badge ${userProfile?.subscription_status}`}>
              {userProfile?.subscription_status?.toUpperCase() || 'ACTIVE'}
            </span>
          </div>
        </div>
        <button
          className="action-btn primary"
          onClick={handleChangePlan}
          disabled={actionLoading.changePlan}
        >
          {actionLoading.changePlan ? "OPENING..." : "CHANGE PLAN"}
        </button>
      </section>

      {/* BILLING SECTION */}
      <section className="billing-section">
        <h3 className="section-title">BILLING</h3>
        {paymentMethod ? (
          <div className="payment-details">
            <div className="card-info">
              <div className="card-brand">
                {paymentMethod.brand?.toUpperCase() || 'CARD'} •••• {paymentMethod.last4}
              </div>
              <div className="card-expiry">
                Expires {paymentMethod.exp_month}/{paymentMethod.exp_year}
              </div>
            </div>
            <button
              className="action-btn secondary"
              onClick={handleEditPayment}
              disabled={actionLoading.changePlan}
            >
              EDIT
            </button>
          </div>
        ) : (
          <p className="no-data">No payment method on file</p>
        )}
      </section>

      {/* BILLING HISTORY SECTION */}
      <section className="billing-section">
        <h3 className="section-title">BILLING HISTORY</h3>
        {invoices.length > 0 ? (
          <div className="invoices-list">
            {invoices.map((invoice) => (
              <div key={invoice.id} className="invoice-row">
                <div className="invoice-info">
                  <span className="invoice-date">{formatDate(invoice.created)}</span>
                  <span className="invoice-description">
                    {invoice.description || `Invoice #${invoice.number}`}
                  </span>
                </div>
                <div className="invoice-actions">
                  <span className="invoice-amount">{formatCurrency(invoice.amount)}</span>
                  <button
                    className="download-btn"
                    onClick={() => handleDownloadInvoice(invoice.id)}
                    disabled={actionLoading[`invoice_${invoice.id}`]}
                  >
                    {actionLoading[`invoice_${invoice.id}`] ? "..." : "DOWNLOAD"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="no-data">No billing history available</p>
        )}
      </section>

      {/* CANCEL MEMBERSHIP SECTION */}
      <section className="billing-section cancel-section">
        <h3 className="section-title warning">CANCEL MEMBERSHIP</h3>
        <div className="cancel-warning">
          <p>
            Cancelling your membership will remove access to all premium features at the end of your current billing period.
          </p>
          {showCancelConfirm && (
            <div className="confirm-cancel">
              <p className="confirm-text">Are you absolutely sure? This action cannot be undone.</p>
              <div className="confirm-actions">
                <button
                  className="action-btn secondary"
                  onClick={() => setShowCancelConfirm(false)}
                >
                  KEEP SUBSCRIPTION
                </button>
                <button
                  className="action-btn danger"
                  onClick={handleCancelSubscription}
                  disabled={actionLoading.cancel}
                >
                  {actionLoading.cancel ? "CANCELLING..." : "YES, CANCEL"}
                </button>
              </div>
            </div>
          )}
          {!showCancelConfirm && (
            <button
              className="action-btn danger"
              onClick={() => setShowCancelConfirm(true)}
            >
              CANCEL MEMBERSHIP
            </button>
          )}
        </div>
      </section>
    </div>
  );
};

export default SubscriptionBilling;
