import React from 'react';

interface SourceLogoProps {
  type: string;
  size?: number;
  className?: string;
  style?: React.CSSProperties;
}

// User-provided official logo SVG files in public/assets/logos/
const ASSET_LOGOS: Record<string, string> = {
  postgres: '/assets/logos/PostgreSQL_logo.3colors.svg',
  postgresql: '/assets/logos/PostgreSQL_logo.3colors.svg',
  mysql: '/assets/logos/mysql-icon.svg',
  excel: '/assets/logos/Microsoft_Office_Excel_(2019–2025).svg',
  xlsx: '/assets/logos/Microsoft_Office_Excel_(2019–2025).svg',
  spreadsheet: '/assets/logos/Microsoft_Office_Excel_(2019–2025).svg',
  snowflake: '/assets/logos/snowflake-icon.svg',
  redshift: '/assets/logos/Amazon-Redshift-Logo.svg',
  bigquery: '/assets/logos/google_bigquery-icon.svg',
  mssql: '/assets/logos/microsoft-sql-server-logo-svgrepo-com.svg',
  sqlserver: '/assets/logos/microsoft-sql-server-logo-svgrepo-com.svg',
};

export const SourceLogo: React.FC<SourceLogoProps> = ({ type, size = 32, className, style }) => {
  const normType = type?.toLowerCase().replace(/[\s_-]+/g, '') || '';

  // 1. Prefer user-provided official logo SVG files in /assets/logos/
  const assetPath = ASSET_LOGOS[normType];
  if (assetPath) {
    return (
      <span
        className={className}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: `${size}px`,
          height: `${size}px`,
          flexShrink: 0,
          ...style,
        }}
      >
        <img
          src={assetPath}
          alt={type}
          style={{
            width: `${size}px`,
            height: `${size}px`,
            objectFit: 'contain',
            display: 'block',
          }}
        />
      </span>
    );
  }

  // 2. Vector SVGs for additional connectors
  const renderSvg = () => {
    switch (normType) {
      case 'databricks':
        return (
          <svg viewBox="0 0 48 48" width={size} height={size} fill="none">
            <path d="M24 4l16 8.8-16 8.8L8 12.8 24 4z" fill="#FF3621" />
            <path
              d="M8 18.5l16 8.8 16-8.8"
              stroke="#FF3621"
              strokeWidth="3.6"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <path
              d="M8 26.5l16 8.8 16-8.8"
              stroke="#FF3621"
              strokeWidth="3.6"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <path
              d="M8 34.5l16 8.8 16-8.8"
              stroke="#FF3621"
              strokeWidth="3.6"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        );

      case 'clickhouse':
        return (
          <svg viewBox="0 0 48 48" width={size} height={size} fill="none">
            <rect x="4.5" y="10" width="3.6" height="28" rx="1.5" fill="#FA4616" />
            <rect x="9.3" y="15" width="3.6" height="18" rx="1.5" fill="#FA4616" />
            <rect x="14.1" y="6" width="3.6" height="36" rx="1.5" fill="#FFCC00" />
            <rect x="18.9" y="12" width="3.6" height="24" rx="1.5" fill="#FFCC00" />
            <rect x="23.7" y="6" width="3.6" height="36" rx="1.5" fill="#FA4616" />
            <rect x="28.5" y="16.5" width="3.6" height="15" rx="1.5" fill="#FFCC00" />
            <rect x="33.3" y="10" width="3.6" height="28" rx="1.5" fill="#FA4616" />
            <rect x="38.1" y="18" width="3.6" height="12" rx="1.5" fill="#FFCC00" />
          </svg>
        );

      case 'athena':
        return (
          <svg viewBox="0 0 48 48" width={size} height={size} fill="none">
            <path d="M24 4l18 10.4v20.8L24 45.6 6 35.2V14.4L24 4z" fill="#8C4FFF" />
            <circle cx="21.5" cy="21.5" r="7.5" stroke="#FFFFFF" strokeWidth="3" fill="none" />
            <path d="M27 27l6.5 6.5" stroke="#FFFFFF" strokeWidth="3.4" strokeLinecap="round" />
            <circle cx="21.5" cy="21.5" r="2.8" fill="#FFFFFF" />
          </svg>
        );

      case 's3':
      case 'amazons3':
        return (
          <svg viewBox="0 0 48 48" width={size} height={size} fill="none">
            <path d="M24 4.5l17 9.8v19.4L24 43.5 7 33.7V14.3L24 4.5z" fill="#E2553E" />
            <path d="M24 4.5l17 9.8-17 9.8-17-9.8L24 4.5z" fill="#EA7564" />
            <path
              d="M24 24.1l17-9.8M24 24.1L7 14.3M24 24.1v19.4"
              stroke="#FFFFFF"
              strokeWidth="2.2"
              strokeLinejoin="round"
            />
            <ellipse cx="24" cy="18.5" rx="7.5" ry="3.3" fill="#B32B18" fillOpacity="0.4" />
          </svg>
        );

      case 'mcpserver':
      case 'mcp':
        return (
          <svg viewBox="0 0 48 48" width={size} height={size} fill="none">
            <rect width="48" height="48" rx="10" fill="#1E293B" />
            <path d="M15 15l18 18M33 15L15 33" stroke="#CC6B49" strokeWidth="3" strokeLinecap="round" />
            <circle cx="15" cy="15" r="5" fill="#D97706" />
            <circle cx="33" cy="15" r="5" fill="#CC6B49" />
            <circle cx="15" cy="33" r="5" fill="#CC6B49" />
            <circle cx="33" cy="33" r="5" fill="#D97706" />
            <circle cx="24" cy="24" r="6" fill="#FFFFFF" />
            <circle cx="24" cy="24" r="3" fill="#1E293B" />
          </svg>
        );

      case 'azuresynapse':
      case 'synapse':
        return (
          <svg viewBox="0 0 48 48" width={size} height={size} fill="none">
            <circle cx="24" cy="24" r="21" fill="#0078D4" />
            <circle cx="24" cy="24" r="6.8" fill="#FFFFFF" />
            <circle cx="13.5" cy="18" r="3.4" fill="#50E6FF" />
            <circle cx="34.5" cy="18" r="3.4" fill="#50E6FF" />
            <circle cx="24" cy="36" r="3.4" fill="#50E6FF" />
            <path
              d="M13.5 18l10.5 6 10.5-6M24 24v12"
              stroke="#FFFFFF"
              strokeWidth="2.2"
              strokeLinecap="round"
            />
          </svg>
        );

      case 'azureblob':
      case 'azureblobstorage':
        return (
          <svg viewBox="0 0 48 48" width={size} height={size} fill="none">
            <rect x="6" y="6" width="36" height="36" rx="6" fill="#0078D4" />
            <ellipse cx="24" cy="16" rx="11" ry="4.8" fill="#50E6FF" />
            <path
              d="M13 16v8.5c0 2.65 4.9 4.8 11 4.8s11-2.15 11-4.8V16"
              stroke="#FFFFFF"
              strokeWidth="2.4"
              fill="none"
            />
            <path
              d="M13 24.5v8.5c0 2.65 4.9 4.8 11 4.8s11-2.15 11-4.8v-8.5"
              stroke="#FFFFFF"
              strokeWidth="2.4"
              fill="none"
            />
          </svg>
        );

      case 'trino':
        return (
          <svg viewBox="0 0 48 48" width={size} height={size} fill="none">
            <path
              d="M9 10.5l13.5 13.5L9 37.5"
              stroke="#DD00A1"
              strokeWidth="5.2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <path
              d="M22.5 10.5L36 24 22.5 37.5"
              stroke="#00D4B2"
              strokeWidth="5.2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        );

      case 'sharepoint':
        return (
          <svg viewBox="0 0 48 48" width={size} height={size} fill="none">
            <circle cx="19.5" cy="18" r="11.5" fill="#008272" />
            <circle cx="28.5" cy="21" r="12" fill="#038387" opacity="0.9" />
            <circle cx="21" cy="30" r="10.5" fill="#004B50" opacity="0.85" />
            <circle cx="24" cy="22.5" r="6" fill="#FFFFFF" opacity="0.9" />
          </svg>
        );

      case 'spanner':
      case 'googlespanner':
      case 'gcpspanner':
        return (
          <svg viewBox="0 0 48 48" width={size} height={size} fill="none">
            <circle cx="24" cy="24" r="21" fill="#E8F0FE" />
            <path d="M24 6l4.5 13.5L42 24l-13.5 4.5L24 42l-4.5-13.5L6 24l13.5-4.5L24 6z" fill="#4285F4" />
            <circle cx="24" cy="24" r="4.5" fill="#1A73E8" />
          </svg>
        );

      case 'teradata':
        return (
          <svg viewBox="0 0 48 48" width={size} height={size} fill="none">
            <circle cx="24" cy="24" r="21" fill="#F37023" />
            <path d="M16.5 16.5h15v4.5h-5.25v13.5h-4.5V21h-5.25v-4.5z" fill="#FFFFFF" />
            <circle cx="31.5" cy="32.25" r="2.25" fill="#FFFFFF" />
          </svg>
        );

      case 'oracle':
        return (
          <svg viewBox="0 0 48 48" width={size} height={size} fill="none">
            <rect x="3" y="10.5" width="42" height="27" rx="13.5" fill="#F80000" />
            <rect x="9.75" y="15.75" width="28.5" height="16.5" rx="8.25" fill="#FFFFFF" />
            <rect x="15" y="19.5" width="18" height="9" rx="4.5" fill="#F80000" />
          </svg>
        );

      case 'github':
        return (
          <svg viewBox="0 0 48 48" width={size} height={size} fill="none">
            <circle cx="24" cy="24" r="21" fill="#181717" />
            <path
              fillRule="evenodd"
              clipRule="evenodd"
              d="M24 9a15 15 0 00-4.74 29.23c.75.14 1.02-.33 1.02-.72v-2.55c-4.17.9-5.05-1-5.05-1-.68-1.74-1.67-2.2-1.67-2.2-1.36-.93.1-.91.1-.91 1.5.1 2.3 1.55 2.3 1.55 1.34 2.3 3.51 1.63 4.36 1.25.14-.97.53-1.64.96-2.02-3.33-.38-6.83-1.67-6.83-7.41 0-1.64.58-2.97 1.55-4.02-.15-.38-.68-1.9.15-3.96 0 0 1.26-.4 4.12 1.54a14.37 14.37 0 017.5 0c2.87-1.94 4.13-1.54 4.13-1.54.83 2.06.3 3.58.15 3.96.96 1.05 1.55 2.38 1.55 4.02 0 5.76-3.51 7.03-6.85 7.4.54.47 1.02 1.38 1.02 2.78v4.13c0 .4.27.87 1.03.72A15 15 0 0024 9z"
              fill="#FFFFFF"
            />
          </svg>
        );

      case 'gitlab':
        return (
          <svg viewBox="0 0 48 48" width={size} height={size} fill="none">
            <path d="M24 39.8l7.2-22.1H16.8L24 39.8z" fill="#E24329" />
            <path d="M24 39.8L16.8 17.7H6.8L24 39.8z" fill="#FC6D26" />
            <path d="M6.8 17.7L3.3 28.4c-.45 1.2 0 2.55 1.05 3.3L24 39.8 6.8 17.7z" fill="#FCA326" />
            <path d="M6.8 17.7h10L13 6.3c-.45-1.35-2.25-1.35-2.7 0L6.8 17.7z" fill="#E24329" />
            <path d="M24 39.8l7.2-22.1h10L24 39.8z" fill="#FC6D26" />
            <path d="M41.2 17.7l3.5 10.7c.45 1.2 0 2.55-1.05 3.3L24 39.8l17.2-22.1z" fill="#FCA326" />
            <path d="M41.2 17.7h-10l3.8-11.4c.45-1.35 2.25-1.35 2.7 0l3.5 11.4z" fill="#E24329" />
          </svg>
        );

      case 'azuredevops':
      case 'devops':
        return (
          <svg viewBox="0 0 48 48" width={size} height={size} fill="none">
            <path d="M7.5 16.5l9-8.25v6.3l13.5-6.3v29.25l-13.5-6.3v6.3l-9-8.25V16.5z" fill="#0078D7" />
            <path d="M16.5 14.55l13.5-6.3v29.25l-13.5-6.3V14.55z" fill="#2560E0" opacity="0.9" />
            <path d="M7.5 16.5l9-1.95v17.7l-9 2.25V16.5z" fill="#005BA1" />
          </svg>
        );

      case 'dremio':
        return (
          <svg viewBox="0 0 48 48" width={size} height={size} fill="none">
            <circle cx="24" cy="24" r="21" fill="#E0F7FA" />
            <path
              d="M10.5 25.5c0-6 6-11.25 13.5-11.25 6.75 0 11.25 3.75 12.75 8.25l4.5-3.75-2.25 7.5c-1.5 4.5-6 9-13.5 9-9 0-15-4.5-15-9.75z"
              fill="#58CBDC"
            />
            <circle cx="27" cy="20.25" r="2.25" fill="#1E293B" />
            <path
              d="M36.75 22.5c-1.5 1.5-4.5 2.25-7.5 1.5"
              stroke="#3098A8"
              strokeWidth="2.25"
              strokeLinecap="round"
            />
          </svg>
        );

      case 'outlook':
      case 'outlookcalendar':
      case 'calendar':
        return (
          <svg viewBox="0 0 48 48" width={size} height={size} fill="none">
            <rect x="18" y="7.5" width="24" height="33" rx="3.75" fill="#0078D4" />
            <path d="M18 16.5h24" stroke="#FFFFFF" strokeWidth="1.8" opacity="0.6" />
            <circle cx="24.75" cy="24" r="1.8" fill="#FFFFFF" />
            <circle cx="30" cy="24" r="1.8" fill="#FFFFFF" />
            <circle cx="35.25" cy="24" r="1.8" fill="#FFFFFF" />
            <circle cx="24.75" cy="30" r="1.8" fill="#FFFFFF" />
            <circle cx="30" cy="30" r="1.8" fill="#FFFFFF" />
            <circle cx="35.25" cy="30" r="1.8" fill="#FFFFFF" />
            <rect x="6" y="12" width="21" height="24" rx="3.75" fill="#106EBE" />
            <circle cx="16.5" cy="24" r="5.25" stroke="#FFFFFF" strokeWidth="2.7" fill="none" />
          </svg>
        );

      case 'sqlite':
        return (
          <svg viewBox="0 0 48 48" width={size} height={size} fill="none">
            <rect x="6" y="6" width="36" height="36" rx="6" fill="#003B57" />
            <path
              d="M14 16c0-2.2 4.5-4 10-4s10 1.8 10 4-4.5 4-10 4-10-1.8-10-4z"
              fill="#0090D6"
            />
            <path
              d="M14 16v8c0 2.2 4.5 4 10 4s10-1.8 10-4v-8"
              stroke="#0090D6"
              strokeWidth="2.4"
              fill="none"
            />
            <path
              d="M14 24v8c0 2.2 4.5 4 10 4s10-1.8 10-4v-8"
              stroke="#0090D6"
              strokeWidth="2.4"
              fill="none"
            />
            <circle cx="33" cy="15" r="2" fill="#00E5FF" />
          </svg>
        );

      default:
        return (
          <svg viewBox="0 0 48 48" width={size} height={size} fill="none">
            <rect x="6" y="6" width="36" height="36" rx="8" fill="#3B82F6" />
            <path
              d="M16 16h16v16H16z"
              stroke="#FFFFFF"
              strokeWidth="2.5"
              strokeLinejoin="round"
            />
          </svg>
        );
    }
  };

  return (
    <span
      className={className}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
        ...style,
      }}
    >
      {renderSvg()}
    </span>
  );
};
