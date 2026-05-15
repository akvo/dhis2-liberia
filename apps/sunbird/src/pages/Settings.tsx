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
    Switch,
    IconAdd16,
    IconDelete16,
    IconEdit16,
    Divider,
    Tag,
} from '@dhis2/ui'
import React, { FC, useState, useEffect } from 'react'
import classes from './Settings.module.css'

export interface AttributeMapping {
    dhis2Attribute: string
    sunbirdField: string
}

export interface ProgramConfig {
    programId: string
    entityType: string
    enabled: boolean
    mappings: AttributeMapping[]
}

export interface SunbirdConfig {
    sunbirdUrl: string
    keycloakUrl: string
    clientId: string
    clientSecret: string
    programs: ProgramConfig[]
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
    programs: [],
}

const defaultProgramConfig: ProgramConfig = {
    programId: '',
    entityType: '',
    enabled: true,
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
    const [selectedProgramIndex, setSelectedProgramIndex] = useState<number | null>(null)
    const [error, setError] = useState<string | null>(null)
    const [saved, setSaved] = useState(false)
    const [prevSaving, setPrevSaving] = useState(false)

    useEffect(() => {
        if (config) {
            setFormData(config)
        }
    }, [config])

    // Show "Saved!" when saving completes
    useEffect(() => {
        if (prevSaving && !saving) {
            setSaved(true)
            const timer = setTimeout(() => setSaved(false), 2000)
            return () => clearTimeout(timer)
        }
        setPrevSaving(saving)
    }, [saving, prevSaving])

    const handleGlobalChange = (field: keyof Omit<SunbirdConfig, 'programs'>, value: string) => {
        setFormData((prev) => ({ ...prev, [field]: value }))
        setError(null)
    }

    const handleProgramChange = (index: number, field: keyof ProgramConfig, value: string | boolean) => {
        setFormData((prev) => {
            const newPrograms = [...prev.programs]
            newPrograms[index] = { ...newPrograms[index], [field]: value }
            return { ...prev, programs: newPrograms }
        })
        setError(null)
    }

    const handleAddProgram = () => {
        setFormData((prev) => ({
            ...prev,
            programs: [...prev.programs, { ...defaultProgramConfig }],
        }))
        setSelectedProgramIndex(formData.programs.length)
    }

    const handleRemoveProgram = (index: number) => {
        setFormData((prev) => ({
            ...prev,
            programs: prev.programs.filter((_, i) => i !== index),
        }))
        if (selectedProgramIndex === index) {
            setSelectedProgramIndex(null)
        } else if (selectedProgramIndex !== null && selectedProgramIndex > index) {
            setSelectedProgramIndex(selectedProgramIndex - 1)
        }
    }

    const getProgramName = (programId: string): string => {
        const program = programs.find((p) => p.id === programId)
        return program?.displayName || programId || i18n.t('New Program')
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

        // Validate each program
        for (let i = 0; i < formData.programs.length; i++) {
            const prog = formData.programs[i]
            if (!prog.programId) {
                setError(i18n.t('Program {{index}}: DHIS2 Program is required', { index: i + 1 }))
                setSelectedProgramIndex(i)
                return
            }
            if (!prog.entityType) {
                setError(i18n.t('Program {{index}}: Entity Type is required', { index: i + 1 }))
                setSelectedProgramIndex(i)
                return
            }
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

    const selectedProgram = selectedProgramIndex !== null ? formData.programs[selectedProgramIndex] : null

    return (
        <div className={classes.container}>
            <h2>{i18n.t('Sunbird RC Settings')}</h2>

            <NoticeBox title={i18n.t('Worker-Based Sync')}>
                {i18n.t(
                    'Sync is handled by a background worker service. Configure the connection details below, then use the Sync page to queue sync requests. Ensure the worker service is running: python adapter/worker.py'
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
                        onChange={({ value }) =>
                            handleGlobalChange('sunbirdUrl', value || '')
                        }
                        placeholder="http://localhost:8081/api/v1"
                        helpText={i18n.t(
                            'Base URL of Sunbird RC (must be accessible from the worker server)'
                        )}
                        required
                    />

                    <InputField
                        label={i18n.t('Keycloak Token URL')}
                        name="keycloakUrl"
                        value={formData.keycloakUrl}
                        onChange={({ value }) =>
                            handleGlobalChange('keycloakUrl', value || '')
                        }
                        placeholder="http://keycloak:8080/auth/realms/sunbird-rc/protocol/openid-connect/token"
                        helpText={i18n.t(
                            'Keycloak token endpoint (must be accessible from the worker server)'
                        )}
                        required
                    />

                    <InputField
                        label={i18n.t('Client ID')}
                        name="clientId"
                        value={formData.clientId}
                        onChange={({ value }) =>
                            handleGlobalChange('clientId', value || '')
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
                            handleGlobalChange('clientSecret', value || '')
                        }
                        placeholder="********"
                        helpText={i18n.t(
                            'OAuth2 client secret for Sunbird RC authentication'
                        )}
                        required
                    />

                    <Divider />

                    <div className={classes.programsHeader}>
                        <h3>{i18n.t('Program Mappings')}</h3>
                        {(() => {
                            const configuredProgramIds = formData.programs.map(p => p.programId)
                            const availablePrograms = programs.filter(p => !configuredProgramIds.includes(p.id))
                            const hasAvailablePrograms = availablePrograms.length > 0
                            return (
                                <Button
                                    small
                                    type="button"
                                    onClick={handleAddProgram}
                                    icon={<IconAdd16 />}
                                    disabled={!hasAvailablePrograms}
                                    title={!hasAvailablePrograms ? i18n.t('All programs are already configured') : undefined}
                                >
                                    {i18n.t('Add Program')}
                                </Button>
                            )
                        })()}
                    </div>

                    {formData.programs.length === 0 ? (
                        <NoticeBox title={i18n.t('No Programs Configured')}>
                            {i18n.t('Click "Add Program" to configure a DHIS2 program for syncing to Sunbird RC.')}
                        </NoticeBox>
                    ) : (
                        <div className={classes.programsList}>
                            {formData.programs.map((prog, index) => (
                                <div
                                    key={index}
                                    className={`${classes.programItem} ${selectedProgramIndex === index ? classes.programItemSelected : ''}`}
                                >
                                    <div className={classes.programItemContent}>
                                        <span className={classes.programName}>
                                            {getProgramName(prog.programId)}
                                        </span>
                                        {prog.entityType && (
                                            <Tag neutral>{prog.entityType}</Tag>
                                        )}
                                        {!prog.enabled && (
                                            <Tag neutral>{i18n.t('Disabled')}</Tag>
                                        )}
                                    </div>
                                    <div className={classes.programItemActions}>
                                        <Button
                                            small
                                            type="button"
                                            onClick={() => setSelectedProgramIndex(
                                                selectedProgramIndex === index ? null : index
                                            )}
                                            icon={<IconEdit16 />}
                                            aria-label={i18n.t('Edit program')}
                                        />
                                        <Button
                                            small
                                            destructive
                                            type="button"
                                            onClick={() => handleRemoveProgram(index)}
                                            icon={<IconDelete16 />}
                                            aria-label={i18n.t('Remove program')}
                                        />
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}

                    {selectedProgram !== null && selectedProgramIndex !== null && (
                        <Card className={classes.programEditCard}>
                            <h4>{i18n.t('Edit Program: {{name}}', { name: getProgramName(selectedProgram.programId) })}</h4>

                            <Field label={i18n.t('DHIS2 Program')} required>
                                <SingleSelect
                                    selected={selectedProgram.programId}
                                    onChange={({ selected }) =>
                                        handleProgramChange(selectedProgramIndex, 'programId', selected || '')
                                    }
                                    placeholder={i18n.t('Select a program')}
                                >
                                    {programs
                                        .filter((program) => {
                                            // Show current selection + programs not yet configured
                                            const isCurrentSelection = program.id === selectedProgram.programId
                                            const isAlreadyConfigured = formData.programs.some(
                                                (p, idx) => p.programId === program.id && idx !== selectedProgramIndex
                                            )
                                            return isCurrentSelection || !isAlreadyConfigured
                                        })
                                        .map((program) => (
                                            <SingleSelectOption
                                                key={program.id}
                                                label={program.displayName}
                                                value={program.id}
                                            />
                                        ))}
                                </SingleSelect>
                            </Field>

                            <InputField
                                label={i18n.t('Sunbird Entity Type')}
                                name="entityType"
                                value={selectedProgram.entityType}
                                onChange={({ value }) =>
                                    handleProgramChange(selectedProgramIndex, 'entityType', value || '')
                                }
                                placeholder="WaterFacility"
                                helpText={i18n.t(
                                    'The entity type in Sunbird RC (e.g., WaterFacility, Student)'
                                )}
                                required
                            />

                            <Switch
                                label={i18n.t('Enabled')}
                                checked={selectedProgram.enabled}
                                onChange={({ checked }) =>
                                    handleProgramChange(selectedProgramIndex, 'enabled', checked)
                                }
                            />
                        </Card>
                    )}

                    <div className={classes.buttonContainer}>
                        <Button
                            type="submit"
                            primary
                            loading={saving}
                            disabled={saving}
                        >
                            {saving
                                ? i18n.t('Saving...')
                                : saved
                                  ? i18n.t('Saved!')
                                  : i18n.t('Save Settings')}
                        </Button>
                    </div>
                </form>
            </Card>
        </div>
    )
}

export default Settings
