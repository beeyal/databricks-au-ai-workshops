# Network Access Control Policy

**Document ID:** POL-IAM-006  
**Version:** 2.3  
**Effective Date:** 1 April 2025  
**Review Date:** 1 April 2026  
**Owner:** Chief Information Security Officer  
**Classification:** Internal

---

## 1. Purpose

This policy governs access to the company's information technology (IT) and operational technology (OT) networks, including remote access, third-party contractor connections, and inter-network communications. It supports compliance with the Security of Critical Infrastructure Act 2018 (Cth), the Australian Energy Sector Cyber Security Framework (AESCSF), and the AER Cyber Security Good Practice Guide for Network Service Providers.

Strong access controls are a primary defence against supply chain attacks and insider threats targeting critical electricity infrastructure. The Australian Cyber Security Centre (ACSC) has identified credential compromise and lateral movement from IT to OT as leading attack vectors against the energy sector.

---

## 2. Network Zones

The company operates a layered network architecture aligned to the AESCSF and IEC 62443 standards:

| Zone | Name | Description |
|---|---|---|
| Zone 0 | Corporate IT | General business systems, email, ERP, corporate Wi-Fi |
| Zone 1 | DMZ | Internet-facing services, AEMO market interfaces, partner connections |
| Zone 2 | OT Supervisory | SCADA/EMS servers, historian, engineering workstations |
| Zone 3 | OT Control | RTUs, PLCs, protection relay management systems |
| Zone 4 | Field Devices | Substation automation, IEDs, smart metering head-end systems |

Traffic between zones is permitted only via approved, documented firewall rules. No direct pathway exists between Zone 0 (Corporate IT) and Zone 3 or Zone 4. Any exception requires CISO approval and is subject to annual review.

---

## 3. User Access Requirements

### 3.1 Privileged Access

Access to Zone 2 or Zone 3 systems is classified as Privileged Access. Privileged Access accounts must:

- Be separate from the user's standard corporate account
- Use multi-factor authentication (MFA) using a hardware token (FIDO2 preferred) or approved authenticator application
- Not be shared between individuals under any circumstances
- Be reviewed quarterly by the line manager and the OT Security Manager
- Automatically expire after 90 days of inactivity and require re-authorisation

### 3.2 Standard User Access

All standard users must authenticate using the corporate Identity Provider (IdP) with MFA enabled. Access to Internal-classified systems is provisioned on a role-based access control (RBAC) basis aligned to the user's job function. Access requests must be submitted via the IT Service Management portal and approved by the relevant data owner.

### 3.3 Privileged Access Workstations (PAWs)

SCADA and EMS management tasks must be performed from designated Privileged Access Workstations located in secure control rooms. PAWs are not connected to the general corporate network and do not have internet access. USB ports are disabled. Software installation on PAWs requires OT Security Manager approval.

---

## 4. Third-Party Contractor Access

### 4.1 Onboarding Requirements

Before being granted any network access, third-party contractors and vendors must:

1. Provide proof of identity (Australian driver's licence or passport)
2. Complete the company's mandatory security awareness training (minimum 30 minutes)
3. Have their employer execute the current Third-Party Access Agreement with the company
4. Pass a background check if accessing Zone 2, 3, or 4 systems (coordinated through HR)
5. Be registered in the Contractor Access Register maintained by Physical Security

### 4.2 Remote Access

Remote access to the company's networks is permitted via the approved corporate VPN only. Third-party remote access to OT zones must additionally use the Privileged Remote Access (PRA) platform (jump server with session recording). The following controls apply:

- Access windows are time-limited (maximum 8-hour session, re-authentication required)
- All sessions are recorded and retained for 90 days
- Concurrent access by the same account to multiple zones is prohibited
- Remote access credentials for third parties are revoked within 4 business hours of contract completion

### 4.3 On-Site Contractor Access

Contractors requiring physical access to substations or control rooms must:

- Hold a valid company-issued visitor pass linked to their access profile
- Be escorted by a company employee when in Zone 3 or Zone 4 areas
- Not connect personal devices to any OT network port
- Use only company-supplied laptops for OT maintenance tasks, or use equipment that has passed a pre-connection malware scan

### 4.4 Critical Infrastructure Protection

Contractors performing work on assets listed in the Critical Infrastructure Register (CIR) — including transmission substations >66 kV, zone substations, and the Network Control Centre — are subject to additional vetting under the Critical Infrastructure Risk Management Program (CIRMP) as required by the SOCI Act. This vetting is administered by the Cyber Security and Physical Security teams in consultation with Legal.

---

## 5. Remote Access for Employees

Employees accessing corporate systems remotely (including from home) must use the corporate VPN client on a company-managed device. Personal devices are not permitted to access Internal or Restricted systems via remote access. Employees travelling internationally must obtain prior approval from the CISO if they need access to Zone 2 or above.

---

## 6. Access Revocation

Access must be revoked within the following timeframes:

| Trigger | Required Revocation Time |
|---|---|
| Employee resignation or termination | Within 1 business day of HR notification |
| Contractor completion | Within 4 business hours |
| Security incident (suspected compromise) | Immediate (within 15 minutes) |
| Role change (access no longer required) | Within 5 business days |

IT Service Management monitors for stale accounts monthly. Accounts inactive for more than 90 days are automatically disabled pending review.

---

## 7. Audit and Compliance

Access control logs for Zones 2–4 are retained for a minimum of 7 years. Quarterly access reviews are conducted by the OT Security team. Annual penetration testing of the IT/OT boundary is required, with results reviewed by the Audit and Risk Committee.

---

*This policy must be read in conjunction with the Cyber Security Incident Response Procedure (PROC-SEC-003), the Vendor Risk Management Policy (POL-VRM-005), and the IT/OT Change Management Procedure (PROC-CHG-008).*
