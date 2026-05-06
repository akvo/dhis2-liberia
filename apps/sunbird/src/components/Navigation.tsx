import i18n from '@dhis2/d2-i18n'
import { TabBar, Tab } from '@dhis2/ui'
import React, { FC } from 'react'
import classes from './Navigation.module.css'

export type PageKey = 'dashboard' | 'sync' | 'history' | 'settings'

interface NavigationProps {
    currentPage: PageKey
    onNavigate: (page: PageKey) => void
}

const Navigation: FC<NavigationProps> = ({ currentPage, onNavigate }) => {
    return (
        <div className={classes.container}>
            <TabBar>
                <Tab
                    selected={currentPage === 'dashboard'}
                    onClick={() => onNavigate('dashboard')}
                >
                    {i18n.t('Dashboard')}
                </Tab>
                <Tab
                    selected={currentPage === 'sync'}
                    onClick={() => onNavigate('sync')}
                >
                    {i18n.t('Sync')}
                </Tab>
                <Tab
                    selected={currentPage === 'history'}
                    onClick={() => onNavigate('history')}
                >
                    {i18n.t('History')}
                </Tab>
                <Tab
                    selected={currentPage === 'settings'}
                    onClick={() => onNavigate('settings')}
                >
                    {i18n.t('Settings')}
                </Tab>
            </TabBar>
        </div>
    )
}

export default Navigation
