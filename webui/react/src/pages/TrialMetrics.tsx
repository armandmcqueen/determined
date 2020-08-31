import { Col, Row, Select } from 'antd';
import React, { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router';

const { Option } = Select;

import Message from 'components/Message';
import useRestApi from 'hooks/useRestApi';
import {
  getExperimentDetails,
  getTrialDetails,
  isNotFound,
} from 'services/api';
import { TrialDetailsParams } from 'services/types';
import { ExperimentDetails, TrialDetails } from 'types';

import Badge, { BadgeType } from '../components/Badge';
import Page from '../components/Page';
import Spinner from '../components/Spinner';
import usePolling from '../hooks/usePolling';

import css from './TrialMetrics.module.scss';

interface Params {
  trialId: string;
}
// from=now-20s&to=now

function genGrafanaEmbedUrl(panelId: string) {
  // const url = 'http://3.236.80.157:3000/d/govu5aZGk/dtrain-time-series-metrics?' +
  const url = 'http://localhost:8080/proxy/grafana/d/govu5aZGk/dtrain-time-series-metrics?' +
        `viewPanel=${panelId}` +
        '&orgId=1' +
        '&refresh=1s' +
        '&from=now-20s' +
        '&to=now' +
        '&var-Database=InfluxDB' +
        '&var-TrainingJob=training_job%7C%3D%7CALBERT_SQuAD_PyTorch_dist_2node' +
        '&var-NetworkInterface=ens3';
  return url;
}
// const grafanaEmbedUrl = 'http://3.236.80.157:3000/d/govu5aZGk/dtrain-time-series-metrics?' +
//  'viewPanel=17' +  // 17=netSent, 4=gpuUtil, 6-gpuMem
//  '&orgId=1' +
//  '&refresh=1s' +
//  '&from=now-20s' +
//  '&to=now' +
//  '&var-Database=InfluxDB' +
//  '&var-TrainingJob=training_job%7C%3D%7CALBERT_SQuAD_PyTorch_dist_2node' +
//  '&var-NetworkInterface=ens3';

const grafanaDefaultPanel = '17';  // Network sent

const TrialMetrics: React.FC = () => {
  const { trialId: trialIdParam } = useParams<Params>();
  const trialId = parseInt(trialIdParam);
  const [ experiment, setExperiment ] = useState<ExperimentDetails>();
  const [ grafanaEmbedUrl, setGrafanaEmbedUrl ] = useState<string>(genGrafanaEmbedUrl(grafanaDefaultPanel));
  const [ trialResponse, triggerTrialRequest ] =
      useRestApi<TrialDetailsParams, TrialDetails>(getTrialDetails, { id: trialId });

  const trial = trialResponse.data;
  const experimentId = trial?.experimentId;

  const pollTrialDetails = useCallback(() => {
    triggerTrialRequest({ id: trialId });
  }, [ triggerTrialRequest, trialId ]);

  function handleChange(panelId: string) {
    setGrafanaEmbedUrl(genGrafanaEmbedUrl(panelId));
  }

  usePolling(pollTrialDetails);

  useEffect(() => {
    if (experimentId === undefined) return;
    getExperimentDetails({ id:experimentId })
      .then(experiment => setExperiment(experiment));
  }, [ experimentId ]);

  if (isNaN(trialId)) return <Message title={`Invalid Trial ID ${trialIdParam}`} />;
  if (trialResponse.error !== undefined) {
    const message = isNotFound(trialResponse.error) ?
      `Unable to find Trial ${trialId}` :
      `Unable to fetch Trial ${trialId}`;
    return <Message message={trialResponse.error.message} title={message} />;
  }
  if (!trial || !experiment) return <Spinner />;

  return (
    <Page
      backPath={`/det/experiments/${experimentId}`}
      breadcrumb={[
        { breadcrumbName: 'Experiments', path: '/det/experiments' },
        {
          breadcrumbName: `Experiment ${experimentId}`,
          path: `/det/experiments/${experimentId}`,
        },
        { breadcrumbName: `Trial ${trialId}`, path: `/det/trials/${trialId}` },
        { breadcrumbName: 'Metrics', path: `/det/trial-metrics/${trialId}` },
      ]}
      showDivider
      subTitle={<Badge state={trial?.state} type={BadgeType.State} />}
      title={`Trial ${trialId} Metrics`}>
      <Row className={css.topRow} gutter={[ 16, 16 ]}>
        <Select defaultValue="17" style={{ width: 270 }} onChange={handleChange}>
          <Option value="17">Network Throughput (Sent)</Option>
          <Option value="16">Network Throughput (Received)</Option>
          <Option value="4">GPU Utilization</Option>
          <Option value="6">GPU Memory</Option>
          <Option value="2">Memory</Option>
          <Option value="8">Disk I/O</Option>
          <Option value="12">Available Disk</Option>
        </Select>
      </Row>
      <Row gutter={[ 16, 16 ]}>
        <iframe frameBorder="0" height="600px" src={grafanaEmbedUrl} width="80%" />
      </Row>
    </Page>
  );
};

export default TrialMetrics;
