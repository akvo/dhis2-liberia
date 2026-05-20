import i18n from '@dhis2/d2-i18n'
import {
    Card,
    InputField,
    Button,
    NoticeBox,
    CircularLoader,
    SingleSelect,
    SingleSelectOption,
} from '@dhis2/ui'
import React, { FC, useState, useEffect } from 'react'
import { useOrgUnitAttributes } from '@/hooks'
import type { SunbirdConfig } from '@/types'
import classes from './Settings.module.css'

interface SettingsProps {
    config?: SunbirdConfig
    loading?: boolean
    saving?: boolean
    onSaveConfig: (config: SunbirdConfig) => void
}

const defaultConfig: SunbirdConfig = {
    sunbirdUrl: '',
    keycloakUrl: '',
    clientId: '',
    clientSecret: '',
    osidAttributeId: '',
}

const Settings: FC<SettingsProps> = ({
    config,
    loading = false,
    saving = false,
    onSaveConfig,
}) => {
    const [formData, setFormData] = useState<SunbirdConfig>(config || defaultConfig)
    const { attributes, loading: attributesLoading } = useOrgUnitAttributes()
    const [error, setError] = useState<string | null>(null)
    const [saved, setSaved] = useState(false)
    const [prevSaving, setPrevSaving] = useState(false)

    useEffect(() => {
        if (config) {
            setFormData(config)
        }
    }, [config])

    useEffect(() => {
        if (prevSaving && !saving) {
            setSaved(true)
            const timer = setTimeout(() => setSaved(false), 2000)
            return () => clearTimeout(timer)
        }
        setPrevSaving(saving)
    }, [saving, prevSaving])

    const handleChange = (field: keyof SunbirdConfig, value: string) => {
        setFormData((prev) => ({ ...prev, [field]: value }))
        setError(null)
    }

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault()

        if (!formData.sunbirdUrl) {
            setError(i18n.t('Sunbird URL is required'))
            return
        }
        if (!formData.keycloakUrl) {
            setError(i18n.t('Keycloak URL is required'))
            return
        }
        if (!formData.clientId) {
            setError(i18n.t('Client ID is required'))
            return
        }
        if (!formData.clientSecret) {
            setError(i18n.t('Client Secret is required'))
            return
        }
        if (!formData.osidAttributeId) {
            setError(i18n.t('OSID Attribute is required'))
            return
        }

        onSaveConfig(formData)
    }

    if (loading) {
        return (
            <div className={classes.loadingContainer}>
                <CircularLoader />
            </div>
        )
    }

    return (
        <div className={classes.container}>
            <h2>{i18n.t('Sunbird RC Settings')}</h2>

            <NoticeBox title={i18n.t('Connection Configuration')}>
                {i18n.t(
                    'Configure the connection to Sunbird RC. Once saved, the Mappings tab will become available to configure entity mappings.'
                )}
            </NoticeBox>

            <Card className={classes.formCard}>
                <form onSubmit={handleSubmit} className={classes.form}>
                    {error && (
                        <NoticeBox error title={i18n.t('Validation Error')}>
                            {error}
                        </NoticeBox>
                    )}

                    <h3>{i18n.t('Connection Settings')}</h3>

                    <InputField
                        label={i18n.t('Sunbird RC Base URL')}
                        name="sunbirdUrl"
                        value={formData.sunbirdUrl}
                        onChange={({ value }) => handleChange('sunbirdUrl', value || '')}
                        placeholder="http://localhost:8081/api/v1"
                        helpText={i18n.t(
                            'Base URL of Sunbird RC API. Note: This host must be added to CORS Whitelist in System Settings > Access.'
                        )}
                        required
                    />

                    <InputField
                        label={i18n.t('Keycloak Token URL')}
                        name="keycloakUrl"
                        value={formData.keycloakUrl}
                        onChange={({ value }) => handleChange('keycloakUrl', value || '')}
                        placeholder="http://keycloak:8080/auth/realms/sunbird-rc/protocol/openid-connect/token"
                        helpText={i18n.t('Keycloak token endpoint')}
                        required
                    />

                    <InputField
                        label={i18n.t('Client ID')}
                        name="clientId"
                        value={formData.clientId}
                        onChange={({ value }) => handleChange('clientId', value || '')}
                        placeholder="demo-api"
                        required
                    />

                    <InputField
                        label={i18n.t('Client Secret')}
                        name="clientSecret"
                        type="password"
                        value={formData.clientSecret}
                        onChange={({ value }) => handleChange('clientSecret', value || '')}
                        placeholder="********"
                        required
                    />

                    <div className={classes.fieldContainer}>
                        <label className={classes.fieldLabel}>
                            {i18n.t('OSID Attribute')} <span className={classes.required}>*</span>
                        </label>
                        <SingleSelect
                            selected={formData.osidAttributeId}
                            onChange={({ selected }) => handleChange('osidAttributeId', selected)}
                            placeholder={i18n.t('Select attribute for storing Sunbird OSID')}
                            loading={attributesLoading}
                        >
                            {attributes.map((attr) => (
                                <SingleSelectOption
                                    key={attr.id}
                                    value={attr.id}
                                    label={`${attr.displayName}${attr.code ? ` (${attr.code})` : ''}`}
                                />
                            ))}
                        </SingleSelect>
                        <span className={classes.helpText}>
                            {i18n.t('Select which Organisation Unit attribute will store the Sunbird Registry ID (OSID) after sync.')}
                        </span>
                    </div>

                    <div className={classes.buttonContainer}>
                        <Button type="submit" primary loading={saving} disabled={saving}>
                            {saving ? i18n.t('Saving...') : saved ? i18n.t('Saved!') : i18n.t('Save Connection')}
                        </Button>
                    </div>
                </form>
            </Card>
        </div>
    )
}

export default Settings
