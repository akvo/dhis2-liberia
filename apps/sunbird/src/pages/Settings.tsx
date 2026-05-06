import i18n from '@dhis2/d2-i18n'
import {
    Card,
    InputField,
    Button,
    NoticeBox,
    CircularLoader,
    Field,
    SingleSelect,
    SingleSelectOption,
} from '@dhis2/ui'
import React, { FC, useState, useEffect } from 'react'
import { useSunbirdApi } from '@/hooks'
import classes from './Settings.module.css'

export interface SunbirdConfig {
    sunbirdUrl: string
    keycloakUrl: string
    clientId: string
    clientSecret: string
    entityType: string
    programId: string
    mappings: AttributeMapping[]
}

export interface AttributeMapping {
    dhis2Attribute: string
    sunbirdField: string
}

interface SettingsProps {
    config?: SunbirdConfig
    loading?: boolean
    saving?: boolean
    onSave: (config: SunbirdConfig) => void
    programs?: Array<{ id: string; displayName: string }>
    trackedEntityAttributes?: Array<{ id: string; displayName: string }>
}

const defaultConfig: SunbirdConfig = {
    sunbirdUrl: '',
    keycloakUrl: '',
    clientId: '',
    clientSecret: '',
    entityType: '',
    programId: '',
    mappings: [],
}

const Settings: FC<SettingsProps> = ({
    config,
    loading = false,
    saving = false,
    onSave,
    programs = [],
    trackedEntityAttributes = [],
}) => {
    const [formData, setFormData] = useState<SunbirdConfig>(
        config || defaultConfig
    )
    const [error, setError] = useState<string | null>(null)
    const { testConnection, testing, testResult, clearResult } = useSunbirdApi()

    useEffect(() => {
        if (config) {
            setFormData(config)
        }
    }, [config])

    const handleTestConnection = () => {
        clearResult()
        if (!formData.sunbirdUrl || !formData.keycloakUrl || !formData.clientId || !formData.clientSecret || !formData.entityType) {
            setError(i18n.t('Please fill in all connection fields before testing'))
            return
        }
        setError(null)
        testConnection(formData)
    }

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
        if (!formData.entityType) {
            setError(i18n.t('Entity Type is required'))
            return
        }
        if (!formData.programId) {
            setError(i18n.t('Program is required'))
            return
        }

        onSave(formData)
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

            <Card className={classes.formCard}>
                <form onSubmit={handleSubmit} className={classes.form}>
                    {error && (
                        <NoticeBox error title={i18n.t('Validation Error')}>
                            {error}
                        </NoticeBox>
                    )}

                    <InputField
                        label={i18n.t('Sunbird RC Base URL')}
                        name="sunbirdUrl"
                        value={formData.sunbirdUrl}
                        onChange={({ value }) =>
                            handleChange('sunbirdUrl', value || '')
                        }
                        placeholder="http://localhost:8081/api/v1"
                        helpText={i18n.t(
                            'The base URL of your Sunbird RC instance'
                        )}
                        required
                    />

                    <InputField
                        label={i18n.t('Keycloak Token URL')}
                        name="keycloakUrl"
                        value={formData.keycloakUrl}
                        onChange={({ value }) =>
                            handleChange('keycloakUrl', value || '')
                        }
                        placeholder="http://keycloak:8080/auth/realms/sunbird-rc/protocol/openid-connect/token"
                        helpText={i18n.t(
                            'The Keycloak OAuth2 token endpoint URL'
                        )}
                        required
                    />

                    <InputField
                        label={i18n.t('Client ID')}
                        name="clientId"
                        value={formData.clientId}
                        onChange={({ value }) =>
                            handleChange('clientId', value || '')
                        }
                        placeholder="demo-api"
                        helpText={i18n.t(
                            'OAuth2 client ID for Sunbird RC authentication'
                        )}
                        required
                    />

                    <InputField
                        label={i18n.t('Client Secret')}
                        name="clientSecret"
                        type="password"
                        value={formData.clientSecret}
                        onChange={({ value }) =>
                            handleChange('clientSecret', value || '')
                        }
                        placeholder="********"
                        helpText={i18n.t(
                            'OAuth2 client secret for Sunbird RC authentication'
                        )}
                        required
                    />

                    <InputField
                        label={i18n.t('Sunbird Entity Type')}
                        name="entityType"
                        value={formData.entityType}
                        onChange={({ value }) =>
                            handleChange('entityType', value || '')
                        }
                        placeholder="WaterFacility"
                        helpText={i18n.t(
                            'The entity type in Sunbird RC (e.g., WaterFacility, Student)'
                        )}
                        required
                    />

                    <div className={classes.testConnectionSection}>
                        <Button
                            onClick={handleTestConnection}
                            loading={testing}
                            disabled={testing}
                            secondary
                        >
                            {testing
                                ? i18n.t('Testing...')
                                : i18n.t('Test Connection')}
                        </Button>

                        {testResult && (
                            <NoticeBox
                                title={testResult.success ? i18n.t('Success') : i18n.t('Connection Failed')}
                                warning={!testResult.success}
                                valid={testResult.success}
                            >
                                <p>{testResult.message}</p>
                                {testResult.details && (
                                    <p className={classes.testDetails}>{testResult.details}</p>
                                )}
                            </NoticeBox>
                        )}
                    </div>

                    <Field label={i18n.t('DHIS2 Program')} required>
                        <SingleSelect
                            selected={formData.programId}
                            onChange={({ selected }) =>
                                handleChange('programId', selected || '')
                            }
                            placeholder={i18n.t('Select a program')}
                        >
                            {programs.map((program) => (
                                <SingleSelectOption
                                    key={program.id}
                                    label={program.displayName}
                                    value={program.id}
                                />
                            ))}
                        </SingleSelect>
                    </Field>

                    <div className={classes.buttonContainer}>
                        <Button
                            type="submit"
                            primary
                            loading={saving}
                            disabled={saving}
                        >
                            {saving
                                ? i18n.t('Saving...')
                                : i18n.t('Save Settings')}
                        </Button>
                    </div>
                </form>
            </Card>
        </div>
    )
}

export default Settings
