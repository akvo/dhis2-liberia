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
    Transfer,
    IconAdd16,
    IconDelete16,
    IconEdit16,
    Divider,
    Tag,
    Modal,
    ModalTitle,
    ModalContent,
    ModalActions,
    ButtonStrip,
    DataTable,
    DataTableHead,
    DataTableBody,
    DataTableRow,
    DataTableCell,
    DataTableColumnHeader,
} from '@dhis2/ui'
import React, { FC, useState, useEffect } from 'react'
import type { SunbirdConfig, EntityMapping, FieldMapping, OrgUnitGroup } from '@/types'
import { SOURCE_FIELDS } from '@/types'
import classes from './Settings.module.css'

interface SettingsProps {
    config?: SunbirdConfig
    entityMappings: EntityMapping[]
    orgUnitGroups: OrgUnitGroup[]
    loading?: boolean
    saving?: boolean
    onSaveConfig: (config: SunbirdConfig) => void
    onSaveMapping: (mapping: EntityMapping) => void
    onDeleteMapping: (id: string) => void
}

const defaultConfig: SunbirdConfig = {
    sunbirdUrl: '',
    keycloakUrl: '',
    clientId: '',
    clientSecret: '',
}

const Settings: FC<SettingsProps> = ({
    config,
    entityMappings,
    orgUnitGroups,
    loading = false,
    saving = false,
    onSaveConfig,
    onSaveMapping,
    onDeleteMapping,
}) => {
    const [formData, setFormData] = useState<SunbirdConfig>(config || defaultConfig)
    const [error, setError] = useState<string | null>(null)
    const [saved, setSaved] = useState(false)
    const [prevSaving, setPrevSaving] = useState(false)

    // Entity mapping modal state
    const [showMappingModal, setShowMappingModal] = useState(false)
    const [editingMapping, setEditingMapping] = useState<EntityMapping | null>(null)

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

        onSaveConfig(formData)
    }

    const handleAddMapping = () => {
        setEditingMapping({
            id: `em-${Date.now()}`,
            entityType: '',
            orgUnitGroupIds: [],
            fieldMappings: [
                { source: 'name', target: 'facilityName', required: true },
                { source: 'code', target: 'facilityCode', required: false },
            ],
        })
        setShowMappingModal(true)
    }

    const handleEditMapping = (mapping: EntityMapping) => {
        setEditingMapping({ ...mapping })
        setShowMappingModal(true)
    }

    const handleDeleteMapping = (id: string) => {
        if (confirm(i18n.t('Are you sure you want to delete this mapping?'))) {
            onDeleteMapping(id)
        }
    }

    const handleSaveMapping = () => {
        if (!editingMapping) return

        if (!editingMapping.entityType) {
            alert(i18n.t('Entity Type is required'))
            return
        }
        if (editingMapping.orgUnitGroupIds.length === 0) {
            alert(i18n.t('At least one Org Unit Group is required'))
            return
        }

        onSaveMapping(editingMapping)
        setShowMappingModal(false)
        setEditingMapping(null)
    }

    const getGroupName = (groupId: string): string => {
        const group = orgUnitGroups.find((g) => g.id === groupId)
        return group?.displayName || groupId
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

            <NoticeBox title={i18n.t('Org Unit-Based Sync')}>
                {i18n.t(
                    'Facilities are synced as Organisation Units. Configure the connection below, then create Entity Mappings to link Org Unit Groups to Sunbird Entity Types.'
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
                        helpText={i18n.t('Base URL of Sunbird RC API')}
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

                    <div className={classes.buttonContainer}>
                        <Button type="submit" primary loading={saving} disabled={saving}>
                            {saving ? i18n.t('Saving...') : saved ? i18n.t('Saved!') : i18n.t('Save Connection')}
                        </Button>
                    </div>
                </form>
            </Card>

            <Divider />

            <div className={classes.mappingsSection}>
                <div className={classes.mappingsHeader}>
                    <h3>{i18n.t('Entity Mappings')}</h3>
                    <Button small icon={<IconAdd16 />} onClick={handleAddMapping}>
                        {i18n.t('Add Mapping')}
                    </Button>
                </div>

                {entityMappings.length === 0 ? (
                    <NoticeBox title={i18n.t('No Mappings Configured')}>
                        {i18n.t(
                            'Click "Add Mapping" to configure which Org Unit Groups sync to which Sunbird Entity Types.'
                        )}
                    </NoticeBox>
                ) : (
                    <div className={classes.mappingsList}>
                        {entityMappings.map((mapping) => (
                            <Card key={mapping.id} className={classes.mappingCard}>
                                <div className={classes.mappingHeader}>
                                    <div>
                                        <strong>{mapping.entityType}</strong>
                                        <div className={classes.mappingGroups}>
                                            {mapping.orgUnitGroupIds.map((gid) => (
                                                <Tag key={gid} neutral>
                                                    {getGroupName(gid)}
                                                </Tag>
                                            ))}
                                        </div>
                                    </div>
                                    <div className={classes.mappingActions}>
                                        <Button
                                            small
                                            icon={<IconEdit16 />}
                                            onClick={() => handleEditMapping(mapping)}
                                        />
                                        <Button
                                            small
                                            destructive
                                            icon={<IconDelete16 />}
                                            onClick={() => handleDeleteMapping(mapping.id)}
                                        />
                                    </div>
                                </div>
                                <div className={classes.mappingFieldCount}>
                                    {i18n.t('{{count}} field mappings', {
                                        count: mapping.fieldMappings.length,
                                    })}
                                </div>
                            </Card>
                        ))}
                    </div>
                )}
            </div>

            {/* Entity Mapping Modal */}
            {showMappingModal && editingMapping && (
                <EntityMappingModal
                    mapping={editingMapping}
                    orgUnitGroups={orgUnitGroups}
                    existingMappings={entityMappings}
                    onSave={handleSaveMapping}
                    onCancel={() => {
                        setShowMappingModal(false)
                        setEditingMapping(null)
                    }}
                    onChange={setEditingMapping}
                />
            )}
        </div>
    )
}

// Entity Mapping Modal Component
interface EntityMappingModalProps {
    mapping: EntityMapping
    orgUnitGroups: OrgUnitGroup[]
    existingMappings: EntityMapping[]
    onSave: () => void
    onCancel: () => void
    onChange: (mapping: EntityMapping) => void
}

const EntityMappingModal: FC<EntityMappingModalProps> = ({
    mapping,
    orgUnitGroups,
    existingMappings,
    onSave,
    onCancel,
    onChange,
}) => {
    // Get groups already assigned to other mappings
    const usedGroupIds = existingMappings
        .filter((m) => m.id !== mapping.id)
        .flatMap((m) => m.orgUnitGroupIds)

    const availableGroups = orgUnitGroups.filter((g) => !usedGroupIds.includes(g.id))

    const handleGroupChange = (selected: string[]) => {
        onChange({ ...mapping, orgUnitGroupIds: selected })
    }

    const handleAddFieldMapping = () => {
        onChange({
            ...mapping,
            fieldMappings: [...mapping.fieldMappings, { source: '', target: '', required: false }],
        })
    }

    const handleFieldMappingChange = (index: number, field: keyof FieldMapping, value: any) => {
        const newMappings = [...mapping.fieldMappings]
        newMappings[index] = { ...newMappings[index], [field]: value }
        onChange({ ...mapping, fieldMappings: newMappings })
    }

    const handleRemoveFieldMapping = (index: number) => {
        const newMappings = mapping.fieldMappings.filter((_, i) => i !== index)
        onChange({ ...mapping, fieldMappings: newMappings })
    }

    return (
        <Modal large onClose={onCancel}>
            <ModalTitle>
                {mapping.entityType
                    ? i18n.t('Edit Entity Mapping: {{type}}', { type: mapping.entityType })
                    : i18n.t('New Entity Mapping')}
            </ModalTitle>
            <ModalContent>
                <div className={classes.modalContent}>
                    <InputField
                        label={i18n.t('Sunbird Entity Type')}
                        value={mapping.entityType}
                        onChange={({ value }) => onChange({ ...mapping, entityType: value || '' })}
                        placeholder="WaterFacility"
                        helpText={i18n.t('The entity type name in Sunbird RC')}
                        required
                    />

                    <Field label={i18n.t('Org Unit Groups')} required>
                        <Transfer
                            selected={mapping.orgUnitGroupIds}
                            onChange={({ selected }) => handleGroupChange(selected)}
                            options={availableGroups.map((g) => ({
                                value: g.id,
                                label: g.displayName,
                            }))}
                            selectedEmptyComponent={
                                <p style={{ textAlign: 'center', padding: '8px' }}>
                                    {i18n.t('Select groups from the left')}
                                </p>
                            }
                            leftHeader={<span>{i18n.t('Available Groups')}</span>}
                            rightHeader={<span>{i18n.t('Selected Groups')}</span>}
                            height="200px"
                        />
                    </Field>

                    <Divider />

                    <div className={classes.fieldMappingsHeader}>
                        <h4>{i18n.t('Field Mappings')}</h4>
                        <Button small icon={<IconAdd16 />} onClick={handleAddFieldMapping}>
                            {i18n.t('Add Field')}
                        </Button>
                    </div>

                    <DataTable>
                        <DataTableHead>
                            <DataTableRow>
                                <DataTableColumnHeader>{i18n.t('DHIS2 Source')}</DataTableColumnHeader>
                                <DataTableColumnHeader>{i18n.t('Sunbird Target')}</DataTableColumnHeader>
                                <DataTableColumnHeader width="80px">{i18n.t('Actions')}</DataTableColumnHeader>
                            </DataTableRow>
                        </DataTableHead>
                        <DataTableBody>
                            {mapping.fieldMappings.map((fm, index) => (
                                <DataTableRow key={index}>
                                    <DataTableCell>
                                        <SingleSelect
                                            selected={fm.source}
                                            onChange={({ selected }) =>
                                                handleFieldMappingChange(index, 'source', selected)
                                            }
                                            placeholder={i18n.t('Select source')}
                                            dense
                                        >
                                            {SOURCE_FIELDS.map((f) => (
                                                <SingleSelectOption
                                                    key={f.value}
                                                    value={f.value}
                                                    label={f.label}
                                                />
                                            ))}
                                        </SingleSelect>
                                    </DataTableCell>
                                    <DataTableCell>
                                        <InputField
                                            value={fm.target}
                                            onChange={({ value }) =>
                                                handleFieldMappingChange(index, 'target', value || '')
                                            }
                                            placeholder="facilityName"
                                            dense
                                        />
                                    </DataTableCell>
                                    <DataTableCell>
                                        <Button
                                            small
                                            destructive
                                            icon={<IconDelete16 />}
                                            onClick={() => handleRemoveFieldMapping(index)}
                                        />
                                    </DataTableCell>
                                </DataTableRow>
                            ))}
                        </DataTableBody>
                    </DataTable>
                </div>
            </ModalContent>
            <ModalActions>
                <ButtonStrip end>
                    <Button onClick={onCancel}>{i18n.t('Cancel')}</Button>
                    <Button primary onClick={onSave}>
                        {i18n.t('Save Mapping')}
                    </Button>
                </ButtonStrip>
            </ModalActions>
        </Modal>
    )
}

export default Settings
